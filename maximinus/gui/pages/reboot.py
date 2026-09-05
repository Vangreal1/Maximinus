"""Final screen: recommends a reboot once the setup/judgment/opt-in
passes are all done, with two ways forward.

This is the one place in the whole GUI that performs a real action
regardless of the "not wired to real execution yet" status of everything
else: actually rebooting the machine, if the user explicitly asks for it.
Everything leading up to this screen stays simulated; this button does
not, because there's no ambiguity about what a button labeled "Reboot"
on a screen recommending a reboot is for.

Because it's real, immediate, and cannot be undone once it happens
(unlike everything else here, which is either reversible or hasn't run
at all), it's gated behind an in-app confirmation dialog — the one place
in this project where "click the primary button" and "the disruptive
thing happens" are not the same click.

"Later" does not loop back to the setup screen. It closes the program:
this screen is the end of a pass, and the user asked for a way to be done
for now rather than be dropped back into another list of checkboxes.
"""

import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from ..errors import format_error


def trigger_reboot() -> subprocess.CompletedProcess:
    """Actually reboot the machine, the same way a desktop's own restart
    menu item does: via systemd-logind, which normal desktop sessions are
    already allowed to do without a password (polkit's default policy for
    an active local session). No sudo involved, same as GNOME/Cinnamon's
    own reboot button."""
    return subprocess.run(["systemctl", "reboot"], capture_output=True, text=True, check=False)


class RebootPage(Gtk.Box):
    def __init__(self, on_later):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_later = on_later

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        header.get_style_context().add_class("header")
        title = Gtk.Label(label="MAXIMINUS", xalign=0)
        title.get_style_context().add_class("header-title")
        subtitle = Gtk.Label(label="That's everything for this pass.", xalign=0)
        subtitle.get_style_context().add_class("header-subtitle")
        header.pack_start(title, False, False, 0)
        header.pack_start(subtitle, False, False, 0)
        self.pack_start(header, False, False, 0)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        body.set_margin_start(14)
        body.set_margin_end(14)
        body.set_margin_top(16)
        body.set_margin_bottom(14)

        headline = Gtk.Label(label="A reboot is recommended.", xalign=0)
        headline.get_style_context().add_class("status-text")
        body.pack_start(headline, False, False, 0)

        explanation = Gtk.Label(
            label=(
                "Some of what may have changed just now, such as a driver module, "
                "a GRUB update, a new swap file, or a storage pool mount, only "
                "takes full effect after a restart. Reboot now, or come back to "
                "it later, whichever suits you."
            ),
            xalign=0,
        )
        explanation.get_style_context().add_class("item-reason")
        explanation.set_line_wrap(True)
        body.pack_start(explanation, False, False, 0)

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
        footer.set_margin_top(10)
        footer.set_margin_bottom(14)
        footer.set_halign(Gtk.Align.END)

        self.later_button = Gtk.Button(label="Later")
        self.later_button.get_style_context().add_class("flat")
        self.later_button.connect("clicked", lambda *_: self._on_later())
        footer.pack_start(self.later_button, False, False, 0)

        self.reboot_button = Gtk.Button(label="Reboot")
        self.reboot_button.get_style_context().add_class("suggested-action")
        self.reboot_button.connect("clicked", self._on_reboot_clicked)
        footer.pack_start(self.reboot_button, False, False, 0)
        self.pack_start(footer, False, False, 0)

    def _on_reboot_clicked(self, _button):
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Reboot now?",
        )
        dialog.format_secondary_text(
            "Any unsaved work in other open applications will be lost. This "
            "restarts the machine immediately."
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        reboot_btn = dialog.add_button("Reboot now", Gtk.ResponseType.OK)
        reboot_btn.get_style_context().add_class("suggested-action")
        dialog.connect("response", self._on_confirm_response)
        dialog.show()

    def _on_confirm_response(self, dialog, response_id):
        dialog.destroy()
        if response_id != Gtk.ResponseType.OK:
            return
        self.error_label.hide()
        try:
            result = trigger_reboot()
        except Exception as exc:  # noqa: BLE001 - catch-all, see gui/errors.py
            self.error_label.set_text(format_error(exc, context="starting the reboot"))
            self.error_label.show()
            return
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            message = f"Reboot command failed (exit {result.returncode})."
            if stderr:
                message += f" {stderr}"
            self.error_label.set_text(message)
            self.error_label.show()
