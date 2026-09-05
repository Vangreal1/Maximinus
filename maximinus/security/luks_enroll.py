"""Enroll a random keyfile into a LUKS drive so it auto-unlocks at boot.

Flow:
  1. User types their existing LUKS passphrase once (getpass, never echoed,
     never written anywhere).
  2. We generate a fresh random keyfile that has nothing to do with that
     passphrase.
  3. `cryptsetup luksAddKey` uses the typed passphrase to *authenticate*
     the change, then adds the random keyfile as an additional way to
     unlock the same drive. The original passphrase still works too.
  4. The keyfile is installed at /etc/maximinus/keys/<uuid>.key, owned by
     root, mode 0400 (unreadable by anyone but root).
  5. /etc/crypttab gets a line pointing at that keyfile, so the kernel
     unlocks the drive automatically on every future boot — no prompt.

The passphrase variable goes out of scope as soon as step 3 finishes; nothing
here ever writes it to disk, an env var, argv, or a log.
"""

import getpass
import os
import stat
import subprocess
import tempfile

from .root_files import RootFileError, read_root_file, write_root_file
from .sudo_session import run_privileged

KEY_DIR = "/etc/maximinus/keys"
CRYPTTAB = "/etc/crypttab"
KEYFILE_SIZE = 64  # bytes of random key material


class EnrollmentError(RuntimeError):
    pass


def get_uuid(device: str) -> str:
    result = subprocess.run(
        ["blkid", "-s", "UUID", "-o", "value", device],
        capture_output=True,
        text=True,
        check=False,
    )
    uuid = result.stdout.strip()
    if not uuid:
        raise EnrollmentError(f"could not determine UUID for {device}")
    return uuid


def keyfile_exists(uuid: str) -> bool:
    keyfile = os.path.join(KEY_DIR, f"{uuid}.key")
    check = subprocess.run(
        ["sudo", "test", "-f", keyfile], check=False
    )
    return check.returncode == 0


def crypttab_registered(uuid: str) -> bool:
    return uuid in read_root_file(CRYPTTAB)


def already_enrolled(uuid: str) -> bool:
    """True only if a previous run finished completely: the keyfile exists
    AND /etc/crypttab actually references it. Checking just the keyfile
    isn't enough — a prior run that was interrupted between installing the
    keyfile and registering crypttab (or a user who later hand-edited
    crypttab and removed the line) would leave the keyfile in place but
    the drive still not actually unlocking automatically. Treating that
    half-finished state as "done" would silently leave the job unfinished.
    """
    return keyfile_exists(uuid) and crypttab_registered(uuid)


def enroll(device: str, passphrase: str | None = None) -> str:
    """Enroll `device` for passphrase-free unlock. Returns the drive's UUID.

    If `passphrase` is None, prompts interactively (not echoed to the
    terminal, not stored). Idempotent: does nothing if already fully
    enrolled, and picks up cleanly from a half-finished previous attempt
    (reuses an existing keyfile instead of asking for the passphrase again
    and generating a redundant one, if only the crypttab entry is missing).
    """
    uuid = get_uuid(device)
    if already_enrolled(uuid):
        return uuid

    dest_keyfile = os.path.join(KEY_DIR, f"{uuid}.key")

    if keyfile_exists(uuid):
        # A previous run got the keyfile installed but not registered.
        # Reuse it rather than asking for the passphrase again.
        try:
            _register_crypttab(uuid, dest_keyfile)
        except RootFileError as exc:
            raise EnrollmentError(str(exc)) from exc
        return uuid

    if passphrase is None:
        passphrase = getpass.getpass(f"Existing LUKS passphrase for {device}: ")

    fd, tmp_keyfile = tempfile.mkstemp(prefix="maximinus-key-")
    try:
        os.write(fd, os.urandom(KEYFILE_SIZE))
        os.close(fd)
        os.chmod(tmp_keyfile, stat.S_IRUSR | stat.S_IWUSR)  # 0600, owner only

        add_key = subprocess.run(
            ["sudo", "cryptsetup", "luksAddKey", device, tmp_keyfile],
            input=passphrase + "\n",
            text=True,
            capture_output=True,
            check=False,
        )
        if add_key.returncode != 0:
            raise EnrollmentError(
                f"cryptsetup luksAddKey failed: {add_key.stderr.strip()}"
            )

        mkdir_result = run_privileged(
            ["mkdir", "-p", "-m", "0700", KEY_DIR], capture_output=True, text=True, check=False
        )
        if mkdir_result.returncode != 0:
            raise EnrollmentError(f"failed to create {KEY_DIR}: {mkdir_result.stderr.strip()}")

        install_result = run_privileged(
            ["install", "-m", "0400", "-o", "root", "-g", "root", tmp_keyfile, dest_keyfile],
            capture_output=True,
            text=True,
            check=False,
        )
        if install_result.returncode != 0:
            raise EnrollmentError(
                f"failed to install keyfile at {dest_keyfile}: {install_result.stderr.strip()}"
            )
    finally:
        passphrase = None  # best-effort: drop the reference promptly
        if os.path.exists(tmp_keyfile):
            os.unlink(tmp_keyfile)

    try:
        _register_crypttab(uuid, dest_keyfile)
    except RootFileError as exc:
        raise EnrollmentError(str(exc)) from exc
    return uuid


def mapper_path_for(uuid: str) -> str:
    return f"/dev/mapper/maximinus-{uuid[:8]}"


def is_unlocked(device: str) -> bool:
    return os.path.exists(mapper_path_for(get_uuid(device)))


def unlock_device(device: str, passphrase: str) -> str:
    """Unlock `device` right now with `passphrase` (a real `cryptsetup
    open`), making its decrypted contents available at the returned mapper
    path. This is also how the passphrase gets checked: cryptsetup itself
    rejects a wrong one, there's no separate "verify" step.

    The passphrase is only ever passed to cryptsetup's stdin; this
    function does not write it anywhere, return it, or retain it after
    this call returns — the caller's own copy is the only one that
    existed, and it's the caller's responsibility to drop that promptly.

    Idempotent: if this device is already unlocked (mapper already
    exists), returns its path immediately without touching cryptsetup
    again or needing the passphrase to still be correct.
    """
    uuid = get_uuid(device)
    mapper_name = f"maximinus-{uuid[:8]}"
    mapper_path = mapper_path_for(uuid)
    if os.path.exists(mapper_path):
        return mapper_path

    result = subprocess.run(
        ["sudo", "cryptsetup", "open", device, mapper_name],
        input=passphrase + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise EnrollmentError(
            f"could not unlock {device}: {result.stderr.strip() or 'wrong passphrase or unlock failed'}"
        )
    return mapper_path


def _register_crypttab(uuid: str, keyfile: str) -> None:
    existing = read_root_file(CRYPTTAB)
    if uuid in existing:
        return
    mapper_name = f"maximinus-{uuid[:8]}"
    line = f"{mapper_name} UUID={uuid} {keyfile} luks\n"
    new_content = existing
    if new_content and not new_content.endswith("\n"):
        new_content += "\n"
    new_content += line
    write_root_file(CRYPTTAB, new_content, mode="0600")
