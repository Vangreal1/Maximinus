"""Setup screen: pick which of the safe, automatic changes to apply.

Driver conflicts, audio, and firewall changes are not listed here. Those
need a judgment call, so they get their own screen after these ones run.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from .. import risk


class SetupRow(Gtk.Box):
    """One selectable row: a checkbox, a title, and a dim reason line."""

    def __init__(self, title, reason, badge, checked=True):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.get_style_context().add_class("item-row")

        self.check = Gtk.CheckButton()
        self.check.set_active(checked)
        self.check.set_valign(Gtk.Align.CENTER)
        self.pack_start(self.check, False, False, 0)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title_label = Gtk.Label(label=title, xalign=0)
        title_label.get_style_context().add_class("item-title")
        title_label.set_line_wrap(True)
        reason_label = Gtk.Label(label=reason, xalign=0)
        reason_label.get_style_context().add_class("item-reason")
        reason_label.set_line_wrap(True)
        text_box.pack_start(title_label, False, False, 0)
        text_box.pack_start(reason_label, False, False, 0)
        self.pack_start(text_box, True, True, 0)

        badge_label = Gtk.Label(label=badge)
        badge_label.get_style_context().add_class("item-badge")
        badge_label.set_valign(Gtk.Align.CENTER)
        self.pack_start(badge_label, False, False, 0)

    @property
    def selected(self):
        return self.check.get_active()


class SetupPage(Gtk.Box):
    def __init__(self, classification, on_start):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_start = on_start
        self._rows = []  # list of (row, kind, payload)

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        header.get_style_context().add_class("header")
        title = Gtk.Label(label="MAXIMINUS", xalign=0)
        title.get_style_context().add_class("header-title")
        subtitle = Gtk.Label(
            label="Pick what to change. Anything that needs a judgment call comes next.",
            xalign=0,
        )
        subtitle.get_style_context().add_class("header-subtitle")
        header.pack_start(title, False, False, 0)
        header.pack_start(subtitle, False, False, 0)
        self.pack_start(header, False, False, 0)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.set_margin_start(10)
        toolbar.set_margin_end(10)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(4)
        select_all_btn = Gtk.Button(label="Select all")
        select_all_btn.get_style_context().add_class("flat")
        select_all_btn.connect("clicked", lambda *_: self._set_all(True))
        select_none_btn = Gtk.Button(label="Select none")
        select_none_btn.get_style_context().add_class("flat")
        select_none_btn.connect("clicked", lambda *_: self._set_all(False))
        toolbar.pack_start(select_all_btn, False, False, 0)
        toolbar.pack_start(select_none_btn, False, False, 0)

        risk_label = Gtk.Label(label="Risk taking:")
        risk_label.get_style_context().add_class("item-reason")
        risk_label.set_margin_start(10)
        self.risk_combo = Gtk.ComboBoxText()
        for level in risk.LEVELS:
            self.risk_combo.append(level, level)
        self.risk_combo.set_active_id(risk.DEFAULT_LEVEL)
        self.risk_combo.connect("changed", self._on_risk_changed)
        toolbar.pack_start(risk_label, False, False, 0)
        toolbar.pack_start(self.risk_combo, False, False, 0)
        self.pack_start(toolbar, False, False, 0)

        self.risk_description = Gtk.Label(label=risk.DESCRIPTIONS[risk.DEFAULT_LEVEL], xalign=0)
        self.risk_description.get_style_context().add_class("header-subtitle")
        self.risk_description.set_line_wrap(True)
        self.risk_description.set_margin_start(10)
        self.risk_description.set_margin_end(10)
        self.risk_description.set_margin_bottom(4)
        self.pack_start(self.risk_description, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        list_box.get_style_context().add_class("row-list")
        list_box.set_margin_start(10)
        list_box.set_margin_end(10)

        for item in classification.apt_items:
            packages = [
                pkg
                for action in item.actions
                if action.get("type") == "apt_install"
                for pkg in action["packages"]
            ]
            row = SetupRow(
                title=item.reason,
                reason="Installs: " + ", ".join(packages),
                badge="INSTALL",
                checked=risk.setup_row_default("apt", risk.DEFAULT_LEVEL),
            )
            list_box.pack_start(row, False, False, 0)
            self._rows.append((row, "apt", item))

        for fixer, item in zip(classification.fixers_to_run, classification.fixer_items):
            row = SetupRow(
                title=item.reason,
                reason=fixer.summary,
                badge="FIX",
                checked=risk.setup_row_default("fixer", risk.DEFAULT_LEVEL),
            )
            list_box.pack_start(row, False, False, 0)
            self._rows.append((row, "fixer", fixer))

        if not self._rows:
            empty = Gtk.Label(label="Nothing found that needs fixing.", xalign=0)
            empty.get_style_context().add_class("item-reason")
            empty.set_margin_top(16)
            list_box.pack_start(empty, False, False, 0)

        scroller.add(list_box)
        self.pack_start(scroller, True, True, 0)

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

        self.start_button = Gtk.Button(label="Start")
        self.start_button.get_style_context().add_class("suggested-action")
        self.start_button.connect("clicked", self._on_start_clicked)
        footer.pack_start(self.start_button, False, False, 0)
        self.pack_start(footer, False, False, 0)

        for row, _kind, _payload in self._rows:
            row.check.connect("toggled", lambda *_: self._update_count())
        self._update_count()

    def _set_all(self, value):
        for row, _kind, _payload in self._rows:
            row.check.set_active(value)

    def get_risk_level(self) -> str:
        return self.risk_combo.get_active_id() or risk.DEFAULT_LEVEL

    def _on_risk_changed(self, _combo):
        level = self.get_risk_level()
        self.risk_description.set_text(risk.DESCRIPTIONS[level])
        for row, kind, _payload in self._rows:
            row.check.set_active(risk.setup_row_default(kind, level))

    def _update_count(self):
        selected = sum(1 for row, _k, _p in self._rows if row.selected)
        self._count_label.set_text(f"{selected} of {len(self._rows)} selected")

    def _on_start_clicked(self, _button):
        selected = [(kind, payload) for row, kind, payload in self._rows if row.selected]
        self._on_start(selected)
