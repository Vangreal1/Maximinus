"""First screen: collect the sudo password and any encrypted-drive
passphrases once, up front, so nothing later in the flow has to stop and
ask again.

What actually happens with each — both are real actions, not simulated:
  - The sudo password is used immediately to authenticate (a real
    `sudo -k -S -v` call — see security/sudo_session.py), then thrown
    away. sudo's own ticket cache is what avoids asking again later, the
    same mechanism the CLI relies on; there's no reason to hold onto the
    password itself past that one check.
  - Each drive's LUKS passphrase is used immediately to unlock that drive
    for real (a real `cryptsetup open` — see
    security/luks_enroll.unlock_device), which is also how it gets
    checked: cryptsetup itself rejects a wrong passphrase, so success at
    unlocking *is* the correctness check. The passphrase itself is never
    stored anywhere, not in this page, not in the session object, not on
    disk — only whether each device is now unlocked is kept (see
    gui/session.py).

Every password field masks its input (Gtk.Entry visibility=False), same
as a terminal password prompt.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from ..errors import format_error
from ...security.luks_enroll import EnrollmentError, unlock_device
from ...security.sudo_session import authenticate_with_password


class CredentialsPage(Gtk.Box):
    def __init__(self, luks_devices, session, on_continue):
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
            label=(
                "Your sudo password is used once, right now, to authenticate, then "
                "discarded. Any drive passphrases below are used once, right now, "
                "to unlock that drive, then discarded — never stored, not even in "
                "memory past this screen."
            ),
            xalign=0,
        )
        explanation.get_style_context().add_class("item-reason")
        explanation.set_line_wrap(True)
        body.pack_start(explanation, False, False, 0)

        sudo_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        sudo_label = Gtk.Label(label="Sudo password", xalign=0)
        sudo_label.get_style_context().add_class("item-title")
        self.sudo_entry = Gtk.Entry()
        self.sudo_entry.set_visibility(False)
        self.sudo_entry.set_activates_default(True)
        sudo_row.pack_start(sudo_label, False, False, 0)
        sudo_row.pack_start(self.sudo_entry, False, False, 0)
        body.pack_start(sudo_row, False, False, 0)

        self._luks_entries = {}
        if luks_devices:
            luks_heading = Gtk.Label(label="Encrypted drives found:", xalign=0)
            luks_heading.get_style_context().add_class("item-title")
            luks_heading.set_margin_top(6)
            body.pack_start(luks_heading, False, False, 0)

            for device in luks_devices:
                row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
                label = Gtk.Label(label=f"Passphrase for {device}", xalign=0)
                label.get_style_context().add_class("item-reason")
                entry = Gtk.Entry()
                entry.set_visibility(False)
                entry.set_activates_default(True)
                row.pack_start(label, False, False, 0)
                row.pack_start(entry, False, False, 0)
                body.pack_start(row, False, False, 0)
                self._luks_entries[device] = entry
        else:
            none_label = Gtk.Label(label="No encrypted drives detected on this machine.", xalign=0)
            none_label.get_style_context().add_class("item-reason")
            none_label.set_margin_top(6)
            body.pack_start(none_label, False, False, 0)

        self.error_label = Gtk.Label(label="", xalign=0)
        self.error_label.get_style_context().add_class("error-text")
        self.error_label.set_line_wrap(True)
        self.error_label.set_no_show_all(True)
        self.error_label.set_margin_top(6)
        body.pack_start(self.error_label, False, False, 0)

        self.pack_start(body, True, True, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.set_margin_start(14)
        footer.set_margin_end(14)
        footer.set_margin_bottom(14)
        footer.set_halign(Gtk.Align.END)

        self.continue_button = Gtk.Button(label="Continue")
        self.continue_button.get_style_context().add_class("suggested-action")
        self.continue_button.connect("clicked", self._on_continue_clicked)
        footer.pack_start(self.continue_button, False, False, 0)
        self.pack_start(footer, False, False, 0)

    def _show_error(self, text: str) -> None:
        self.error_label.set_text(text)
        self.error_label.show()

    def _on_continue_clicked(self, _button):
        self.error_label.hide()
        password = self.sudo_entry.get_text()
        if not password:
            self._show_error("Enter your sudo password to continue.")
            return

        self.continue_button.set_sensitive(False)
        try:
            authenticated = authenticate_with_password(password)
        except Exception as exc:  # noqa: BLE001 - catch-all, see gui/errors.py
            self.continue_button.set_sensitive(True)
            self._show_error(format_error(exc, context="checking your sudo password"))
            return
        finally:
            self.sudo_entry.set_text("")  # never keep the password around longer than needed

        self.continue_button.set_sensitive(True)
        if not authenticated:
            self._show_error("Incorrect password, or sudo authentication failed.")
            return

        self._session.sudo_authenticated = True

        for device, entry in self._luks_entries.items():
            if device in self._session.unlocked_devices:
                continue  # already unlocked from a previous attempt on this screen
            passphrase = entry.get_text()
            entry.set_text("")  # drop it from the widget the moment we've read it
            if not passphrase:
                self._show_error(f"Enter the passphrase for {device} to continue.")
                self.continue_button.set_sensitive(True)
                return
            try:
                unlock_device(device, passphrase)
            except EnrollmentError as exc:
                self._show_error(str(exc))
                self.continue_button.set_sensitive(True)
                return
            except Exception as exc:  # noqa: BLE001 - catch-all, see gui/errors.py
                self._show_error(format_error(exc, context=f"unlocking {device}"))
                self.continue_button.set_sensitive(True)
                return
            finally:
                passphrase = None  # best-effort: drop the local reference promptly
            self._session.unlocked_devices.add(device)

        self._on_continue()
