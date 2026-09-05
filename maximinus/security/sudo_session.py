"""Ask for the sudo passphrase once per run, using sudo's own ticket cache.

We deliberately do NOT read the password ourselves and store/pipe it — we
let `sudo -v` prompt the user directly at the terminal. Once that succeeds,
sudo caches a ticket (typically ~15 minutes, configurable in /etc/sudoers)
and every subsequent `sudo ...` call in this process tree proceeds without
another prompt. This is standard sudo behavior, not something Maximinus
invents or manages itself.
"""

import subprocess


class ElevationError(RuntimeError):
    pass


def ensure_sudo() -> None:
    """Prompt for the sudo passphrase now if we don't already have a ticket.

    Raises ElevationError if the user cancels or authentication fails.
    """
    result = subprocess.run(["sudo", "-v"], check=False)
    if result.returncode != 0:
        raise ElevationError("sudo authentication failed or was cancelled")


def has_live_ticket() -> bool:
    """True if a sudo ticket is already cached (no prompt would be shown)."""
    result = subprocess.run(
        ["sudo", "-n", "true"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def run_privileged(cmd, **kwargs):
    """Run cmd (a list) under sudo, assuming ensure_sudo() already ran.

    Defaults to check=True (raise on failure) but respects an explicit
    check=False from the caller — several callers intentionally inspect
    .returncode themselves instead of catching CalledProcessError.
    """
    kwargs.setdefault("check", True)
    return subprocess.run(["sudo", *cmd], **kwargs)
