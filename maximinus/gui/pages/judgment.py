"""Judgment screen: the items that need a human decision, one row each,
with a checkbox and an explanation of what could happen if you go ahead.

Shown after the safe changes finish. Unlike the setup screen, nothing here
is pre-selected. Each one carries a real trade-off (see rules.yaml's
manual_step descriptions, which this screen shows word for word), so the
user has to opt in deliberately rather than uncheck their way out of it.

Clicking OK hands the selection straight to the window, which runs it
through the same progress screen used for the setup screen's items (see
ProgressPage) rather than simulating anything here itself — that keeps
there being exactly one place that shows "here's what's happening now."
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from .. import risk
from ..errors import format_error


class JudgmentRow(Gtk.Box):
    def __init__(self, item):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.get_style_context().add_class("item-row")
        self.item = item

        self.check = Gtk.CheckButton()
        self.check.set_active(False)
        self.check.set_valign(Gtk.Align.START)
        self.check.set_margin_top(1)
        self.pack_start(self.check, False, False, 0)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
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

        badge = Gtk.Label(label="YOUR CALL")
        badge.get_style_context().add_class("item-badge-risk")
        badge.set_valign(Gtk.Align.START)
        badge.set_margin_top(1)
        self.pack_start(badge, False, False, 0)

    @property
    def selected(self):
        return self.check.get_active()


class JudgmentPage(Gtk.Box):
    def __init__(self, items, on_done):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_done = on_done
        self._rows = []

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        header.get_style_context().add_class("header")
        title = Gtk.Label(label="MAXIMINUS", xalign=0)
        title.get_style_context().add_class("header-title")
        subtitle = Gtk.Label(
            label="These need a decision. Nothing is picked for you, read each one first.",
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
        list_box.set_margin_start(10)
        list_box.set_margin_end(10)
        list_box.set_margin_top(6)

        for item in items:
            row = JudgmentRow(item)
            list_box.pack_start(row, False, False, 0)
            self._rows.append(row)

        if not self._rows:
            empty = Gtk.Label(label="Nothing needs a judgment call this time.", xalign=0)
            empty.get_style_context().add_class("item-reason")
            empty.set_margin_top(16)
            list_box.pack_start(empty, False, False, 0)

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

        self.ok_button = Gtk.Button(label="OK")
        self.ok_button.get_style_context().add_class("suggested-action")
        self.ok_button.connect("clicked", self._on_ok_clicked)
        footer.pack_start(self.ok_button, False, False, 0)
        self.pack_start(footer, False, False, 0)

        for row in self._rows:
            row.check.connect("toggled", lambda *_: self._update_count())
        self._update_count()

    def apply_risk_default(self, level):
        """Called when the setup screen hands off to this one, so the
        Risk Taking level chosen there also applies here. Only "High"
        pre-checks anything; every other level leaves these unchecked,
        since they're the items that specifically need a judgment call."""
        checked = risk.judgment_default(level)
        for row in self._rows:
            row.check.set_active(checked)
        self._update_count()

    def _update_count(self):
        selected = sum(1 for row in self._rows if row.selected)
        self._count_label.set_text(f"{selected} of {len(self._rows)} selected")

    def _on_ok_clicked(self, _button):
        selected = [row.item for row in self._rows if row.selected]
        self.status_label.get_style_context().remove_class("error-text")
        try:
            self._on_done(selected)
        except Exception as exc:  # noqa: BLE001 - catch-all, see gui/errors.py
            self.status_label.set_text(format_error(exc, context="continuing past this screen"))
            self.status_label.get_style_context().add_class("error-text")
            self.status_label.show()
