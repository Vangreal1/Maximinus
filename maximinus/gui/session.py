"""Tracks what the first screen accomplished, in memory only, for the
lifetime of the running GUI process.

Nothing sensitive is ever held here. The sudo password is used once to
authenticate and immediately discarded (sudo's own ticket cache covers
the rest of the run). Drive passphrases are used once, immediately, to
unlock their drive (see security/luks_enroll.unlock_device) and are never
stored here or anywhere else — only which devices that succeeded for is
kept, never the passphrase that made it succeed.
"""

from dataclasses import dataclass, field


@dataclass
class Session:
    sudo_authenticated: bool = False
    unlocked_devices: set = field(default_factory=set)  # device paths, not passphrases

    def clear(self) -> None:
        self.sudo_authenticated = False
        self.unlocked_devices.clear()
