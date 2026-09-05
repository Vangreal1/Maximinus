"""Unlock a BitLocker-encrypted partition right now, via dislocker.

The common case this exists for: a dual-boot machine with a Windows
drive that has BitLocker turned on. dislocker exposes the decrypted
contents as a virtual file (a loop-mountable disk image) at a mountpoint
we create — it does not itself mount a filesystem, the same way
`cryptsetup open` for LUKS exposes a decrypted block device without
mounting it. Actually mounting the resulting filesystem is a separate,
later step, not part of "unlock."

BitLocker accepts two different kinds of secret: a user password, or a
48-digit numerical recovery key (shown in 8 groups of 6 digits,
dash-separated, when BitLocker was first turned on). dislocker needs to
know which one it's been given (`-u` for a password, `-p` for a recovery
key) — see _looks_like_recovery_key().

Same rule as everywhere else here: the passphrase is only ever passed to
dislocker as a command-line argument for that one call and is never
written to disk, logged, or retained by this module afterward. (Passing
a secret as an argv value is visible to other processes on the same
machine via /proc for the instant the command runs — an unavoidable
trade-off of dislocker's own interface, which has no stdin-based input
mode the way cryptsetup does. This is the same exposure any `dislocker`
command line typing this out at a shell prompt would have.)
"""

import os
import re
import shutil
import subprocess

from .sudo_session import run_privileged

MOUNT_ROOT = "/mnt/maximinus-bitlocker"
_RECOVERY_KEY_RE = re.compile(r"^\d{6}(-\d{6}){7}$")


class UnlockError(RuntimeError):
    pass


def _looks_like_recovery_key(secret: str) -> bool:
    return bool(_RECOVERY_KEY_RE.match(secret.strip()))


def _slug_for(device: str) -> str:
    return device.replace("/dev/", "").replace("/", "-")


def mountpoint_for(device: str) -> str:
    return os.path.join(MOUNT_ROOT, _slug_for(device))


def dislocker_installed() -> bool:
    return shutil.which("dislocker-fuse") is not None or shutil.which("dislocker") is not None


def ensure_dislocker_installed() -> None:
    if dislocker_installed():
        return
    result = run_privileged(
        ["apt-get", "install", "-y", "dislocker"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise UnlockError(f"failed to install dislocker: {result.stderr.strip()}")


def is_unlocked(device: str) -> bool:
    virtual_file = os.path.join(mountpoint_for(device), "dislocker-file")
    return os.path.exists(virtual_file)


def unlock_device(device: str, secret: str) -> str:
    """Unlock BitLocker `device` right now with `secret` (a password or a
    48-digit recovery key — auto-detected, see _looks_like_recovery_key).
    Returns the mountpoint containing the decrypted virtual disk image
    (`<mountpoint>/dislocker-file`), which a later step can loop-mount to
    actually access the filesystem.

    Wrong-secret and any other dislocker failure both raise UnlockError;
    dislocker's own message is included; that message is the correctness
    check, the same way cryptsetup's exit status is for LUKS.

    Idempotent: if this device is already unlocked (its virtual file
    already exists), returns the existing mountpoint without calling
    dislocker again or needing the secret to still be correct.
    """
    mountpoint = mountpoint_for(device)
    if is_unlocked(device):
        return mountpoint

    ensure_dislocker_installed()

    mkdir_result = run_privileged(
        ["mkdir", "-p", mountpoint], capture_output=True, text=True, check=False
    )
    if mkdir_result.returncode != 0:
        raise UnlockError(f"failed to create {mountpoint}: {mkdir_result.stderr.strip()}")

    flag = "-p" if _looks_like_recovery_key(secret) else "-u"
    result = subprocess.run(
        ["sudo", "dislocker-fuse", "-V", device, f"{flag}{secret}", "--", mountpoint],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise UnlockError(
            f"could not unlock {device}: {result.stderr.strip() or 'wrong password/recovery key or unlock failed'}"
        )
    return mountpoint
