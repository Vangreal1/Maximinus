"""Opt-in features screen: standalone capabilities like storage pooling
that change how the system behaves on an ongoing basis, rather than
fixing a one-off problem.

Kept entirely separate from the judgment-call screen on purpose. A
judgment call is "should I apply this fix, yes or no" for something that
already happened (a driver conflict, a firewall left off). An opt-in
feature is different: turning it on changes what you'll see every time
you open a folder from now on. That deserves its own explicit read and
its own explicit decision, not a checkbox in a list of unrelated fixes.

Like the rest of the GUI, this is not wired to real execution yet: the
Enable button simulates turning the feature on rather than actually
running `maximinus pool-drives`.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402


class FeatureCard(Gtk.Box):
    """One opt-in feature: title, its full explanation, and its own
    checkbox. Unchecked by default, same as a judgment call, because
    turning this on is never something to default to."""

    def __init__(self, item):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.get_style_context().add_class("item-row")
        self.item = item

        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.check = Gtk.CheckButton()
        self.check.set_active(False)
        self.check.set_valign(Gtk.Align.START)
        header_row.pack_start(self.check, False, False, 0)

        title_label = Gtk.Label(label=item.reason, xalign=0)
        title_label.get_style_context().add_class("item-title")
        title_label.set_line_wrap(True)
        header_row.pack_start(title_label, True, True, 0)

        badge = Gtk.Label(label="OPT-IN FEATURE")
        badge.get_style_context().add_class("item-badge-risk")
        badge.set_valign(Gtk.Align.START)
        header_row.pack_start(badge, False, False, 0)

        self.pack_start(header_row, False, False, 0)

        for action in item.actions:
            explanation = action.get("description", "")
            if explanation:
                explanation_label = Gtk.Label(label=explanation, xalign=0)
                explanation_label.get_style_context().add_class("item-risk")
                explanation_label.set_line_wrap(True)
                explanation_label.set_margin_start(22)
                self.pack_start(explanation_label, False, False, 0)

    @property
    def selected(self):
        return self.check.get_active()


class FeaturesPage(Gtk.Box):
    def __init__(self, items, on_done):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_done = on_done
        self._cards = []

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        header.get_style_context().add_class("header")
        title = Gtk.Label(label="MAXIMINUS", xalign=0)
        title.get_style_context().add_class("header-title")
        subtitle = Gtk.Label(
            label="Optional features. Nothing here turns on unless you check it and confirm.",
            xalign=0,
        )
        subtitle.get_style_context().add_class("header-subtitle")
        header.pack_start(title, False, False, 0)
        header.pack_start(subtitle, False, False, 0)
        self.pack_start(header, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        list_box.get_style_context().add_class("row-list")
        list_box.set_margin_start(10)
        list_box.set_margin_end(10)
        list_box.set_margin_top(8)
        list_box.set_margin_bottom(4)

        for item in items:
            card = FeatureCard(item)
            list_box.pack_start(card, False, False, 0)
            self._cards.append(card)

        scroller.add(list_box)
        self.pack_start(scroller, True, True, 0)

        self.status_label = Gtk.Label(label="", xalign=0)
        self.status_label.get_style_context().add_class("header-subtitle")
        self.status_label.set_margin_start(10)
        self.status_label.set_no_show_all(True)
        self.pack_start(self.status_label, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.set_margin_start(10)
        footer.set_margin_end(10)
        footer.set_margin_top(8)
        footer.set_margin_bottom(10)
        footer.set_halign(Gtk.Align.END)

        self._count_label = Gtk.Label(label="")
        self._count_label.get_style_context().add_class("item-reason")
        self._count_label.set_halign(Gtk.Align.START)
        footer.pack_start(self._count_label, True, True, 0)

        self.skip_button = Gtk.Button(label="Skip")
        self.skip_button.get_style_context().add_class("flat")
        self.skip_button.connect("clicked", lambda *_: self._on_done([]))
        footer.pack_start(self.skip_button, False, False, 0)

        self.enable_button = Gtk.Button(label="Enable selected")
        self.enable_button.get_style_context().add_class("suggested-action")
        self.enable_button.connect("clicked", self._on_enable_clicked)
        footer.pack_start(self.enable_button, False, False, 0)
        self.pack_start(footer, False, False, 0)

        for card in self._cards:
            card.check.connect("toggled", lambda *_: self._update_count())
        self._update_count()

    def _update_count(self):
        selected = sum(1 for card in self._cards if card.selected)
        self._count_label.set_text(f"{selected} of {len(self._cards)} selected")

    def _on_enable_clicked(self, _button):
        selected = [card.item for card in self._cards if card.selected]
        if not selected:
            self._on_done([])
            return
        self.enable_button.set_sensitive(False)
        word = "feature" if len(selected) == 1 else "features"
        self.status_label.set_text(f"Turning on {len(selected)} {word}.")
        self.status_label.show()
        GLib.timeout_add(500, self._finish, selected)

    def _finish(self, selected):
        word = "feature" if len(selected) == 1 else "features"
        self.status_label.set_text(f"Done. {len(selected)} {word} enabled. (Preview only, nothing really changed.)")
        self.enable_button.set_sensitive(True)
        self._on_done(selected)
        return False
