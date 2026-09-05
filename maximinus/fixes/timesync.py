"""Turn on NTP time sync.

A clock that's drifted enough (common right after a fresh install before
anything has synced) causes confusing, hard-to-diagnose failures: apt
rejecting repository signatures as "not valid yet", TLS handshake
failures, etc. Enabling NTP is the standard, harmless fix.
"""

from ..security.sudo_session import run_privileged
from .errors import FixError
from .registry import Fixer


def apply() -> None:
    result = run_privileged(
        ["timedatectl", "set-ntp", "true"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise FixError(f"timedatectl set-ntp true failed: {result.stderr.strip()}")


FIXER = Fixer(
    id="time-sync-disabled",
    fact="time.ntp_disabled",
    summary="Enable NTP time sync (`timedatectl set-ntp true`).",
    apply=apply,
)
