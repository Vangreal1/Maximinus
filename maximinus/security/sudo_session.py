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


def authenticate_with_password(password: str) -> bool:
    """Verify `password` is a valid sudo password for the current user, by
    actually using it. Unlike ensure_sudo(), this reads the password we
    were given rather than letting sudo prompt at the terminal — for a GUI
    password field, there is no terminal for sudo to prompt at.

    `-k` first discards any cached ticket, so this genuinely tests the
    password given rather than succeeding for free because an earlier
    sudo call in this session already cached one. Returns True/False;
    never raises for a wrong password. The password is only ever passed
    to sudo's own stdin, never written to disk, logged, or returned.
    """
    result = subprocess.run(
        ["sudo", "-k", "-S", "-v"],
        input=password + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


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
