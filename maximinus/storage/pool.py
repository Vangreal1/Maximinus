"""Build a mergerfs pool over a category folder (e.g. Downloads) so it
shows the combined contents of that folder from every branch, with no
files copied or moved.

We mount mergerfs directly at the category folder's own path (e.g.
~/Downloads). This is the standard mergerfs pattern for "fold an existing
directory into the pool": the folder's own current contents are simply
included as one of the branches, so they remain fully visible (and
writable) through the merged view. Unmounting the pool (or removing the
fstab line and rebooting) restores the plain folder exactly as it was —
nothing on disk is touched by pooling itself.
"""

import os
import shutil
import subprocess

from ..security.root_files import read_root_file, write_root_file
from ..security.sudo_session import run_privileged

FSTAB = "/etc/fstab"


class PoolError(RuntimeError):
    pass


def mergerfs_installed() -> bool:
    return shutil.which("mergerfs") is not None


def ensure_mergerfs_installed() -> None:
    if mergerfs_installed():
        return
    result = run_privileged(
        ["apt-get", "install", "-y", "mergerfs"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PoolError(f"failed to install mergerfs: {result.stderr.strip()}")


def is_pooled(mount_path: str) -> bool:
    fstab = read_root_file(FSTAB)
    return any(
        line.split()[1] == mount_path
        for line in fstab.splitlines()
        if line.strip() and not line.strip().startswith("#") and len(line.split()) > 1
    )


def _underlying_mountpoint(path: str) -> str:
    """The real mount point backing `path` (e.g. /mnt/otherdrive for
    /mnt/otherdrive/home/user/Downloads), via findmnt's own path resolution."""
    result = subprocess.run(
        ["findmnt", "-n", "-o", "TARGET", "--target", path],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "/"


def _fstab_has_mountpoint(fstab: str, mountpoint: str) -> bool:
    if mountpoint == "/":
        return True  # root is always available at boot by definition
    return any(
        line.split()[1] == mountpoint
        for line in fstab.splitlines()
        if line.strip() and not line.strip().startswith("#") and len(line.split()) > 1
    )


def check_boot_safety(branches: list[str]) -> list[str]:
    """Warn about branches that aren't guaranteed to be mounted at boot.

    A branch on a drive that isn't itself in /etc/fstab (e.g. it was mounted
    by hand, or by the desktop's auto-mount daemon after login) won't be
    there yet when the pool's mount unit runs. With the nofail/
    requires-mounts-for options build_pool() sets, this can never hang or
    fail the boot — that branch is just silently left out of the pool until
    it's mounted — but it's worth surfacing to the user.
    """
    fstab = read_root_file(FSTAB)
    warnings = []
    for branch in branches:
        mountpoint = _underlying_mountpoint(branch)
        if not _fstab_has_mountpoint(fstab, mountpoint):
            warnings.append(
                f"{branch} lives on {mountpoint}, which has no /etc/fstab entry — "
                "it may not be available yet at boot, so it could be missing from "
                "the pool until it's mounted (this will not block or fail booting)."
            )
    return warnings


def build_pool(mount_path: str, branches: list[str], policy: str = "mfs") -> None:
    """Merge `branches` (existing directories) into one view at `mount_path`.

    `mount_path` is typically one of the branches itself (e.g. ~/Downloads),
    so its existing contents remain part of the merged view. `policy`
    controls which branch receives newly created files; "mfs" (most free
    space) is what makes the pool behave like combined free space rather
    than always filling up the first drive.

    The fstab entry is written with `nofail` plus one
    `x-systemd.requires-mounts-for=<branch>` per branch and short device/
    mount timeouts. That combination means: systemd orders this mount after
    each branch's own mount, waits only briefly for a branch that isn't
    ready, and — critically — never blocks or fails the boot if a branch
    (or mergerfs itself) doesn't come up. Worst case the merged folder is
    just not mounted yet; it never turns into an unbootable system.
    """
    if is_pooled(mount_path):
        return
    if len(branches) < 2:
        raise PoolError("need at least 2 branches to form a pool")
    for branch in branches:
        if not os.path.isdir(branch):
            raise PoolError(f"branch does not exist: {branch}")

    ensure_mergerfs_installed()

    branch_spec = ":".join(branches)
    requires_mounts = ",".join(f"x-systemd.requires-mounts-for={b}" for b in branches)
    options = (
        f"defaults,allow_other,use_ino,category.create={policy},nonempty,"
        f"nofail,{requires_mounts},"
        "x-systemd.device-timeout=10,x-systemd.mount-timeout=10"
    )
    line = f"{branch_spec} {mount_path} fuse.mergerfs {options} 0 0\n"

    fstab = read_root_file(FSTAB)
    if not fstab.endswith("\n") and fstab:
        fstab += "\n"
    fstab += line
    write_root_file(FSTAB, fstab, mode="0644")
    run_privileged(["systemctl", "daemon-reload"], capture_output=True, check=False)

    result = run_privileged(
        ["mount", mount_path], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise PoolError(f"mount failed: {result.stderr.strip()}")


def unpool(mount_path: str) -> None:
    """Undo pooling: unmount and remove the fstab line. No data is touched —
    each branch's files stay exactly where they already were on disk."""
    subprocess.run(["sudo", "umount", mount_path], check=False)
    fstab = read_root_file(FSTAB)
    kept = [
        line
        for line in fstab.splitlines(keepends=True)
        if not (line.split() and len(line.split()) > 1 and line.split()[1] == mount_path)
    ]
    write_root_file(FSTAB, "".join(kept), mode="0644")
