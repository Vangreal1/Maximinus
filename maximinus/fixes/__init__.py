"""Real, narrow fixes for common fresh-install problems.

Only problems that are safe to fix unattended (standard, well-documented,
reversible, and unlikely to break something the user is actively relying
on) get an entry here. Everything riskier — an audio server swap that
could kill the session mid-fix, enabling a firewall that could lock out an
SSH session — stays a manual_step in rules.yaml with an explicit command
for the user to run themselves.

Each Fixer.apply() assumes ensure_sudo() already ran and raises FixError
on failure. Importing this package populates FIXERS as a side effect.
"""

from .apt_repair import FIXER as _apt_repair_fixer
from .dkms_headers import FIXER as _dkms_headers_fixer
from .errors import FixError
from .grub_dualboot import FIXER as _grub_dualboot_fixer
from .registry import FIXERS, Fixer, register
from .swapfile import FIXER as _swapfile_fixer
from .timesync import FIXER as _timesync_fixer

for _fixer in (
    _apt_repair_fixer,
    _dkms_headers_fixer,
    _timesync_fixer,
    _grub_dualboot_fixer,
    _swapfile_fixer,
):
    register(_fixer)

__all__ = ["FIXERS", "Fixer", "FixError", "register"]
