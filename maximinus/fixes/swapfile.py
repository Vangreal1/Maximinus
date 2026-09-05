"""Create a swap file on a low-memory machine that has no swap at all.

Unlike the other fixers, this one creates new content on disk rather than
installing a package or editing an existing config file. Kept safe and
reversible the same way as everything else here:

- A fixed, modest size (2 GiB) rather than trying to be clever about
  exactly how much a given workload needs.
- Handles the one common filesystem-shaped obstacle empirically: btrfs
  (Mint's Timeshift-friendly default on some installs) refuses to
  fallocate a swap file on a copy-on-write file and needs the file
  marked no-COW *before* it's written. We do that unconditionally (it's
  a harmless no-op on ext4/xfs/etc.) and fall back to a slower `dd` fill
  if `fallocate` still refuses.
- /etc/fstab gets `nofail`, so a missing/corrupted swap file can never
  block or fail a boot.
- Undoing it is three ordinary commands: `sudo swapoff /swapfile`,
  remove the /etc/fstab line, `sudo rm /swapfile`.
"""

import os

from ..security.root_files import RootFileError, read_root_file, write_root_file
from ..security.sudo_session import run_privileged
from .errors import FixError
from .registry import Fixer

SWAPFILE_PATH = "/swapfile"
SWAPFILE_SIZE_MB = 2048
FSTAB = "/etc/fstab"


def _already_configured() -> bool:
    if os.path.exists(SWAPFILE_PATH):
        return True
    return SWAPFILE_PATH in read_root_file(FSTAB)


def _allocate(path: str, size_mb: int) -> None:
    """Reserve `size_mb` MiB for `path`, however this filesystem allows it."""
    fallocate = run_privileged(
        ["fallocate", "-l", f"{size_mb}M", path], capture_output=True, text=True, check=False
    )
    if fallocate.returncode == 0:
        return

    # Some filesystems (notably btrfs on a copy-on-write file) refuse
    # fallocate for swap. dd is slower but works everywhere; the file was
    # already marked no-COW before we got here, so this is safe on btrfs too.
    dd = run_privileged(
        ["dd", "if=/dev/zero", f"of={path}", "bs=1M", f"count={size_mb}", "status=none"],
        capture_output=True,
        text=True,
        check=False,
    )
    if dd.returncode != 0:
        raise FixError(
            f"could not allocate {path}: fallocate failed ({fallocate.stderr.strip()}), "
            f"and the dd fallback also failed ({dd.stderr.strip()})"
        )


def apply() -> None:
    if _already_configured():
        return

    create = run_privileged(
        ["install", "-m", "600", "-o", "root", "-g", "root", "/dev/null", SWAPFILE_PATH],
        capture_output=True,
        text=True,
        check=False,
    )
    if create.returncode != 0:
        raise FixError(f"failed to create {SWAPFILE_PATH}: {create.stderr.strip()}")

    # Mark no-COW before writing any data. Required for a swap file on
    # btrfs; a harmless no-op (fails quietly, which we ignore) on any
    # filesystem that doesn't understand chattr's +C attribute.
    run_privileged(["chattr", "+C", SWAPFILE_PATH], capture_output=True, text=True, check=False)

    _allocate(SWAPFILE_PATH, SWAPFILE_SIZE_MB)

    mkswap = run_privileged(["mkswap", SWAPFILE_PATH], capture_output=True, text=True, check=False)
    if mkswap.returncode != 0:
        raise FixError(f"mkswap failed: {mkswap.stderr.strip()}")

    swapon = run_privileged(["swapon", SWAPFILE_PATH], capture_output=True, text=True, check=False)
    if swapon.returncode != 0:
        raise FixError(f"swapon failed: {swapon.stderr.strip()}")

    fstab = read_root_file(FSTAB)
    if not fstab.endswith("\n") and fstab:
        fstab += "\n"
    fstab += f"{SWAPFILE_PATH} none swap sw,nofail 0 0\n"
    try:
        write_root_file(FSTAB, fstab, mode="0644")
    except RootFileError as exc:
        raise FixError(str(exc)) from exc


FIXER = Fixer(
    id="low-memory-no-swap",
    fact="mem.low_ram_no_swap",
    summary=f"Create a {SWAPFILE_SIZE_MB // 1024} GiB swap file, since this machine has little RAM and none configured.",
    apply=apply,
)
