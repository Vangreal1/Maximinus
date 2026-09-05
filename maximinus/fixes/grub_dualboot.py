"""Make GRUB list a detected other OS (typical case: Windows dual-boot).

Recent GRUB defaults ship with os-prober disabled, or the package isn't
installed at all, so a fresh Mint install next to Windows silently boots
straight past the Windows entry with no menu option for it. The fix is the
standard three steps: install os-prober, make sure GRUB_DISABLE_OS_PROBER
isn't set to true in /etc/default/grub, and regenerate the GRUB config.
Editing /etc/default/grub is done via a plain text substitution and backed
by update-grub actually reading the result, so a mistake here is caught
immediately (update-grub fails loudly) rather than silently breaking boot.
"""

from ..security.root_files import RootFileError, read_root_file, write_root_file
from ..security.sudo_session import run_privileged
from .errors import FixError
from .registry import Fixer

GRUB_DEFAULTS = "/etc/default/grub"


def _ensure_os_prober_enabled() -> None:
    content = read_root_file(GRUB_DEFAULTS)
    lines = content.splitlines()
    new_lines = []
    found = False
    for line in lines:
        if line.strip().lstrip("#").strip().startswith("GRUB_DISABLE_OS_PROBER"):
            new_lines.append("GRUB_DISABLE_OS_PROBER=false")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append("GRUB_DISABLE_OS_PROBER=false")
    write_root_file(GRUB_DEFAULTS, "\n".join(new_lines) + "\n", mode="0644")


def apply() -> None:
    install = run_privileged(
        ["apt-get", "install", "-y", "os-prober"],
        capture_output=True,
        text=True,
        check=False,
    )
    if install.returncode != 0:
        raise FixError(f"failed to install os-prober: {install.stderr.strip()}")

    try:
        _ensure_os_prober_enabled()
    except RootFileError as exc:
        raise FixError(str(exc)) from exc

    update = run_privileged(
        ["update-grub"], capture_output=True, text=True, check=False
    )
    if update.returncode != 0:
        raise FixError(f"update-grub failed: {update.stderr.strip()}")


FIXER = Fixer(
    id="grub-os-prober-disabled",
    fact="grub.os_prober_disabled_with_other_os",
    summary=(
        "Install os-prober, enable it in /etc/default/grub, and run "
        "update-grub so the other detected OS shows up in the boot menu."
    ),
    apply=apply,
)
