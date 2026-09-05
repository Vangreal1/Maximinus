"""Judgment screen: the items that need a human decision, one row each,
with a checkbox and an explanation of what could happen if you go ahead.

Shown after the immediate/safe changes finish. Unlike the setup screen,
nothing here is pre-selected — these are opt-in by design, since each one
carries a real trade-off (see rules.yaml's manual_step descriptions, which
this screen surfaces verbatim).

NOT WIRED TO REAL EXECUTION YET — clicking OK simulates applying the
selection with a short delay rather than actually running anything.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402


class JudgmentRow(Gtk.Box):
    def __init__(self, item):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.get_style_context().add_class("item-row")
        self.item = item

        self.check = Gtk.CheckButton()
        self.check.set_active(False)
        self.check.set_valign(Gtk.Align.START)
        self.check.set_margin_top(2)
        self.pack_start(self.check, False, False, 0)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        title_label = Gtk.Label(label=item.reason, xalign=0)
        title_label.get_style_context().add_class("item-title")
        title_label.set_line_wrap(True)
        text_box.pack_start(title_label, False, False, 0)

        for action in item.actions:
            risk_text = action.get("description", "")
            if risk_text:
                risk_label = Gtk.Label(label=risk_text, xalign=0)
                risk_label.get_style_context().add_class("item-risk")
                risk_label.set_line_wrap(True)
                risk_label.set_max_width_chars(70)
                text_box.pack_start(risk_label, False, False, 0)

        self.pack_start(text_box, True, True, 0)

        badge = Gtk.Label(label="JUDGMENT CALL")
        badge.get_style_context().add_class("item-badge-risk")
        badge.set_valign(Gtk.Align.START)
        badge.set_margin_top(2)
        self.pack_start(badge, False, False, 0)

    @property
    def selected(self):
        return self.check.get_active()


class JudgmentPage(Gtk.Box):
    def __init__(self, items, on_done):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_done = on_done
        self._rows = []

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        header.get_style_context().add_class("header")
        title = Gtk.Label(label="MAXIMINUS — JUDGMENT CALLS", xalign=0)
        title.get_style_context().add_class("header-title")
        subtitle = Gtk.Label(
            label="Nothing here is pre-selected. Read what could happen, then choose.",
            xalign=0,
        )
        subtitle.get_style_context().add_class("header-subtitle")
        header.pack_start(title, False, False, 0)
        header.pack_start(subtitle, False, False, 0)
        self.pack_start(header, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        list_box.get_style_context().add_class("row-list")
        list_box.set_margin_start(14)
        list_box.set_margin_end(14)
        list_box.set_margin_top(10)

        for item in items:
            row = JudgmentRow(item)
            list_box.pack_start(row, False, False, 0)
            self._rows.append(row)

        if not self._rows:
            empty = Gtk.Label(label="No judgment calls this time.", xalign=0)
            empty.get_style_context().add_class("item-reason")
            empty.set_margin_top(20)
            list_box.pack_start(empty, False, False, 0)

        scroller.add(list_box)
        self.pack_start(scroller, True, True, 0)

        self.status_label = Gtk.Label(label="", xalign=0)
        self.status_label.get_style_context().add_class("header-subtitle")
        self.status_label.set_margin_start(14)
        self.status_label.set_no_show_all(True)
        self.pack_start(self.status_label, False, False, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer.set_margin_start(14)
        footer.set_margin_end(14)
        footer.set_margin_top(10)
        footer.set_margin_bottom(14)
        footer.set_halign(Gtk.Align.END)

        self._count_label = Gtk.Label(label="")
        self._count_label.get_style_context().add_class("item-reason")
        self._count_label.set_halign(Gtk.Align.START)
        footer.pack_start(self._count_label, True, True, 0)

        self.ok_button = Gtk.Button(label="OK")
        self.ok_button.get_style_context().add_class("suggested-action")
        self.ok_button.connect("clicked", self._on_ok_clicked)
        footer.pack_start(self.ok_button, False, False, 0)
        self.pack_start(footer, False, False, 0)

        for row in self._rows:
            row.check.connect("toggled", lambda *_: self._update_count())
        self._update_count()

    def _update_count(self):
        selected = sum(1 for row in self._rows if row.selected)
        self._count_label.set_text(f"{selected} of {len(self._rows)} selected")

    def _on_ok_clicked(self, _button):
        selected = [row.item for row in self._rows if row.selected]
        if not selected:
            self._on_done([])
            return
        self.ok_button.set_sensitive(False)
        self.status_label.set_text(f"Applying {len(selected)} selected item(s)…")
        self.status_label.show()
        GLib.timeout_add(500, self._finish, selected)

    def _finish(self, selected):
        self.status_label.set_text(f"Done — {len(selected)} item(s) applied (simulated).")
        self.ok_button.set_sensitive(True)
        self._on_done(selected)
        return False
