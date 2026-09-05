"""Install the kernel headers matching the running kernel.

DKMS (used by the NVIDIA driver, VirtualBox modules, etc.) silently fails
to build its kernel module if the matching linux-headers-<version> package
isn't installed — a very common cause of "the driver is installed but
doesn't work" on a fresh install where headers were never pulled in.
"""

import platform

from ..security.sudo_session import run_privileged
from .errors import FixError
from .registry import Fixer


def apply() -> None:
    package = f"linux-headers-{platform.release()}"
    result = run_privileged(
        ["apt-get", "install", "-y", package],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise FixError(f"failed to install {package}: {result.stderr.strip()}")


FIXER = Fixer(
    id="dkms-headers-missing",
    fact="dkms.headers_missing",
    summary="Install linux-headers-$(uname -r) so DKMS modules (NVIDIA, VirtualBox, ...) can build.",
    apply=apply,
)
