"""Final screen: recommends a reboot once the setup/judgment/opt-in
passes are all done.

Several things this tool touches only take full effect after a restart —
a newly loaded kernel module, a GRUB regeneration, a new swap file, a
storage pool mount. Rather than guess at exactly what still needs a
reboot, this screen always shows up at the end of a full pass and leaves
the decision (and the actual rebooting) to the user: there's no "Restart
Now" button here. Actually rebooting a real machine isn't something to
trigger from a UI whose execution isn't wired up for real yet, and won't
be added just to make this screen feel more complete — it also isn't a
Maximinus-versus-not-Maximinus decision, so it always belongs to the
user, not a button.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402


class RebootPage(Gtk.Box):
    def __init__(self, on_done):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_done = on_done

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
        body.set_margin_top(20)
        body.set_margin_bottom(14)

        headline = Gtk.Label(label="A reboot is recommended.", xalign=0)
        headline.get_style_context().add_class("status-text")
        body.pack_start(headline, False, False, 0)

        explanation = Gtk.Label(
            label=(
                "Some of what may have changed just now, such as a driver module, "
                "a GRUB update, a new swap file, or a storage pool mount, only "
                "takes full effect after a restart. It's safe to keep using this "
                "machine first; reboot whenever it suits you."
            ),
            xalign=0,
        )
        explanation.get_style_context().add_class("item-reason")
        explanation.set_line_wrap(True)
        body.pack_start(explanation, False, False, 0)

        self.pack_start(body, True, True, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.set_margin_start(14)
        footer.set_margin_end(14)
        footer.set_margin_bottom(14)
        footer.set_halign(Gtk.Align.END)

        self.done_button = Gtk.Button(label="Done")
        self.done_button.get_style_context().add_class("suggested-action")
        self.done_button.connect("clicked", lambda *_: self._on_done())
        footer.pack_start(self.done_button, False, False, 0)
        self.pack_start(footer, False, False, 0)
