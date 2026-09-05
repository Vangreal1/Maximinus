"""Fix an interrupted/half-configured apt or dpkg run.

This is the official, standard remedy Ubuntu itself documents for the
"dpkg was interrupted, you must manually run 'sudo dpkg --configure -a'"
message — running it again when nothing is actually broken is a no-op.
"""

from ..security.sudo_session import run_privileged
from .errors import FixError
from .registry import Fixer


def apply() -> None:
    configure = run_privileged(
        ["dpkg", "--configure", "-a"], capture_output=True, text=True, check=False
    )
    if configure.returncode != 0:
        raise FixError(f"dpkg --configure -a failed: {configure.stderr.strip()}")

    fix_broken = run_privileged(
        ["apt-get", "install", "-f", "-y"], capture_output=True, text=True, check=False
    )
    if fix_broken.returncode != 0:
        raise FixError(f"apt-get install -f failed: {fix_broken.stderr.strip()}")


FIXER = Fixer(
    id="apt-broken-state",
    fact="apt.broken_state",
    summary="Finish an interrupted dpkg/apt run: `dpkg --configure -a` then `apt-get install -f`.",
    apply=apply,
)
