"""First screen: collect the sudo password and any encrypted-drive
secrets once, up front, so nothing later in the flow has to stop and ask
again.

What actually happens with each — both are real actions, not simulated:
  - The sudo password is used immediately to authenticate (a real
    `sudo -k -S -v` call — see security/sudo_session.py), then thrown
    away. sudo's own ticket cache is what avoids asking again later, the
    same mechanism the CLI relies on; there's no reason to hold onto the
    password itself past that one check.
  - Each drive's passphrase (LUKS) or password/recovery key (BitLocker)
    is used immediately to unlock that drive for real — a real
    `cryptsetup open` or `dislocker-fuse` call, see
    security/luks_enroll.unlock_device and security/bitlocker.unlock_device
    — which is also how it gets checked: the unlock tool itself rejects a
    wrong secret, so success at unlocking *is* the correctness check. The
    secret itself is never stored anywhere, not in this page, not in the
    session object, not on disk — only whether each device is now
    unlocked is kept (see gui/session.py).

Every password field masks its input (Gtk.Entry visibility=False), same
as a terminal password prompt. A wrong entry shows its rejection message
directly under that specific field, not as a single banner for the whole
screen, so it's obvious exactly which one needs fixing.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from ..errors import format_error
from ...security import bitlocker
from ...security.luks_enroll import EnrollmentError, unlock_device as unlock_luks
from ...security.sudo_session import authenticate_with_password

_KIND_LABELS = {
    "luks": "LUKS",
    "bitlocker": "BitLocker",
}


def _unlock(kind, device, secret):
    """Dispatch to the right unlocker for this drive type. Raises
    EnrollmentError (LUKS) or bitlocker.UnlockError on a wrong secret or
    any other failure — both are plain RuntimeError subclasses with a
    human-readable message, so callers can catch either the same way."""
    if kind == "bitlocker":
        bitlocker.unlock_device(device, secret)
    else:
        unlock_luks(device, secret)


class _DriveRow(Gtk.Box):
    """One encrypted drive: its label, its secret entry, and its own
    rejection message shown directly beneath it."""

    def __init__(self, device, kind):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.device = device
        self.kind = kind

        field_name = "Password or recovery key" if kind == "bitlocker" else "Passphrase"
        label = Gtk.Label(label=f"{field_name} for {device} ({_KIND_LABELS[kind]})", xalign=0)
        label.get_style_context().add_class("item-reason")
        self.pack_start(label, False, False, 0)

        self.entry = Gtk.Entry()
        self.entry.set_visibility(False)
        self.entry.set_activates_default(True)
        self.pack_start(self.entry, False, False, 0)

        self.error_label = Gtk.Label(label="", xalign=0)
        self.error_label.get_style_context().add_class("error-text")
        self.error_label.set_line_wrap(True)
        self.error_label.set_no_show_all(True)
        self.pack_start(self.error_label, False, False, 0)

    def show_error(self, text: str) -> None:
        self.error_label.set_text(text)
        self.error_label.show()

    def clear_error(self) -> None:
        self.error_label.hide()


class CredentialsPage(Gtk.Box):
    def __init__(self, encrypted_devices, session, on_continue):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._session = session
        self._on_continue = on_continue

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        header.get_style_context().add_class("header")
        title = Gtk.Label(label="MAXIMINUS", xalign=0)
        title.get_style_context().add_class("header-title")
        subtitle = Gtk.Label(
            label="Enter your password once so nothing later has to ask again.",
            xalign=0,
        )
        subtitle.get_style_context().add_class("header-subtitle")
        header.pack_start(title, False, False, 0)
        header.pack_start(subtitle, False, False, 0)
        self.pack_start(header, False, False, 0)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        body.set_margin_start(14)
        body.set_margin_end(14)
        body.set_margin_top(16)
        body.set_margin_bottom(14)

        explanation = Gtk.Label(
            label="Your sudo password is used once, right now, to authenticate, then discarded.",
            xalign=0,
        )
        explanation.get_style_context().add_class("item-reason")
        explanation.set_line_wrap(True)
        body.pack_start(explanation, False, False, 0)

        sudo_label = Gtk.Label(label="Sudo password", xalign=0)
        sudo_label.get_style_context().add_class("item-title")
        body.pack_start(sudo_label, False, False, 0)

        self.sudo_entry = Gtk.Entry()
        self.sudo_entry.set_visibility(False)
        self.sudo_entry.set_activates_default(True)
        body.pack_start(self.sudo_entry, False, False, 0)

        self.sudo_error_label = Gtk.Label(label="", xalign=0)
        self.sudo_error_label.get_style_context().add_class("error-text")
        self.sudo_error_label.set_line_wrap(True)
        self.sudo_error_label.set_no_show_all(True)
        body.pack_start(self.sudo_error_label, False, False, 0)

        self._drive_rows = {}
        if encrypted_devices:
            luks_heading = Gtk.Label(label="Encrypted drives found:", xalign=0)
            luks_heading.get_style_context().add_class("item-title")
            luks_heading.set_margin_top(6)
            body.pack_start(luks_heading, False, False, 0)

            disclaimer = Gtk.Label(
                label=(
                    "Nothing you enter below is ever stored, on disk or in memory, "
                    "past the moment it's used to unlock its drive."
                ),
                xalign=0,
            )
            disclaimer.get_style_context().add_class("item-risk")
            disclaimer.set_line_wrap(True)
            body.pack_start(disclaimer, False, False, 0)

            for device, kind in encrypted_devices:
                row = _DriveRow(device, kind)
                body.pack_start(row, False, False, 0)
                self._drive_rows[device] = row
        else:
            none_label = Gtk.Label(label="No encrypted drives detected on this machine.", xalign=0)
            none_label.get_style_context().add_class("item-reason")
            none_label.set_margin_top(6)
            body.pack_start(none_label, False, False, 0)

        self.pack_start(body, True, True, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.set_margin_start(14)
        footer.set_margin_end(14)
        footer.set_margin_top(10)
        footer.set_margin_bottom(14)
        footer.set_halign(Gtk.Align.END)

        self.continue_button = Gtk.Button(label="Continue")
        self.continue_button.get_style_context().add_class("suggested-action")
        self.continue_button.connect("clicked", self._on_continue_clicked)
        footer.pack_start(self.continue_button, False, False, 0)
        self.pack_start(footer, False, False, 0)

    def _clear_all_errors(self) -> None:
        self.sudo_error_label.hide()
        for row in self._drive_rows.values():
            row.clear_error()

    def _on_continue_clicked(self, _button):
        self._clear_all_errors()
        password = self.sudo_entry.get_text()
        if not password:
            self.sudo_error_label.set_text("Enter your sudo password to continue.")
            self.sudo_error_label.show()
            return

        self.continue_button.set_sensitive(False)
        try:
            authenticated = authenticate_with_password(password)
        except Exception as exc:  # noqa: BLE001 - catch-all, see gui/errors.py
            self.continue_button.set_sensitive(True)
            self.sudo_error_label.set_text(format_error(exc, context="checking your sudo password"))
            self.sudo_error_label.show()
            return
        finally:
            self.sudo_entry.set_text("")  # never keep the password around longer than needed

        self.continue_button.set_sensitive(True)
        if not authenticated:
            self.sudo_error_label.set_text("Incorrect password, or sudo authentication failed.")
            self.sudo_error_label.show()
            return

        self._session.sudo_authenticated = True

        for device, row in self._drive_rows.items():
            if device in self._session.unlocked_devices:
                continue  # already unlocked from a previous attempt on this screen
            secret = row.entry.get_text()
            row.entry.set_text("")  # drop it from the widget the moment we've read it
            if not secret:
                row.show_error("Enter this drive's passphrase (or key) to continue.")
                self.continue_button.set_sensitive(True)
                return
            try:
                _unlock(row.kind, device, secret)
            except (EnrollmentError, bitlocker.UnlockError) as exc:
                row.show_error(str(exc))
                self.continue_button.set_sensitive(True)
                return
            except Exception as exc:  # noqa: BLE001 - catch-all, see gui/errors.py
                row.show_error(format_error(exc, context=f"unlocking {device}"))
                self.continue_button.set_sensitive(True)
                return
            finally:
                secret = None  # best-effort: drop the local reference promptly
            self._session.unlocked_devices.add(device)

        self._on_continue()
