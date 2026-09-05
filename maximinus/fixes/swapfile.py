"""Create a swap file on a low-memory machine that has no swap at all.

Unlike the other fixers, this one creates new content on disk rather than
installing a package or editing an existing config file. Kept safe and
reversible the same way as everything else here:

- A fixed, modest size (2 GiB) rather than trying to be clever about
  exactly how much a given workload needs.
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


def apply() -> None:
    if _already_configured():
        return

    alloc = run_privileged(
        ["fallocate", "-l", f"{SWAPFILE_SIZE_MB}M", SWAPFILE_PATH],
        capture_output=True,
        text=True,
        check=False,
    )
    if alloc.returncode != 0:
        raise FixError(
            f"failed to allocate {SWAPFILE_PATH} ({alloc.stderr.strip()}); "
            "some filesystems (e.g. some btrfs setups) don't support fallocate for swap"
        )

    chmod = run_privileged(["chmod", "600", SWAPFILE_PATH], capture_output=True, text=True, check=False)
    if chmod.returncode != 0:
        raise FixError(f"failed to set permissions on {SWAPFILE_PATH}: {chmod.stderr.strip()}")

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
