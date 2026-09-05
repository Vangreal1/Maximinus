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


def build_pool(mount_path: str, branches: list[str], policy: str = "mfs") -> None:
    """Merge `branches` (existing directories) into one view at `mount_path`.

    `mount_path` is typically one of the branches itself (e.g. ~/Downloads),
    so its existing contents remain part of the merged view. `policy`
    controls which branch receives newly created files; "mfs" (most free
    space) is what makes the pool behave like combined free space rather
    than always filling up the first drive.
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
    options = f"defaults,allow_other,use_ino,category.create={policy},nonempty"
    line = f"{branch_spec} {mount_path} fuse.mergerfs {options} 0 0\n"

    fstab = read_root_file(FSTAB)
    if not fstab.endswith("\n") and fstab:
        fstab += "\n"
    fstab += line
    write_root_file(FSTAB, fstab, mode="0644")

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
