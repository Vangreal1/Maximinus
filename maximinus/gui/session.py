"""Holds credentials entered on the first screen, in memory only, for the
lifetime of the running GUI process.

Nothing here is ever written to disk, logged, or included in an error
message — `Session` deliberately has no __repr__/__str__ override, so the
default object repr (no field values) is what would print if anyone ever
did something careless like `print(session)`.

The sudo password itself is NOT retained past the moment it's used to
authenticate: `sudo -v` caches its own ticket on success, so holding the
password afterward would just be extra exposure for no benefit. Only the
per-drive LUKS passphrases are kept, since a later pass (drive enrollment)
needs them and there's no equivalent ticket-cache mechanism for those.
"""

from dataclasses import dataclass, field


@dataclass
class Session:
    sudo_authenticated: bool = False
    luks_passphrases: dict = field(default_factory=dict)  # device path -> passphrase

    def set_luks_passphrase(self, device: str, passphrase: str) -> None:
        self.luks_passphrases[device] = passphrase

    def clear(self) -> None:
        """Drop everything held in memory. Call this once these
        credentials have actually been used for what they were collected
        for, so they don't sit around in memory any longer than needed."""
        self.sudo_authenticated = False
        self.luks_passphrases.clear()
