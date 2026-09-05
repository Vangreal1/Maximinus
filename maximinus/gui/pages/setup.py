"""Setup screen: pick which of the safe/automatic changes to apply.

Judgment-call items (driver conflicts, audio, firewall) are deliberately
NOT listed here — they get their own screen after the immediate changes
run, per the intended flow: settle the safe stuff first, then walk through
the riskier decisions one at a time with their consequences spelled out.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402


class SetupRow(Gtk.Box):
    """One selectable row: a checkbox, a title, and a dim reason line."""

    def __init__(self, title, reason, badge, checked=True):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.get_style_context().add_class("item-row")
        self.set_margin_top(0)

        self.check = Gtk.CheckButton()
        self.check.set_active(checked)
        self.check.set_valign(Gtk.Align.CENTER)
        self.pack_start(self.check, False, False, 0)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
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

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        header.get_style_context().add_class("header")
        title = Gtk.Label(label="MAXIMINUS — SETUP", xalign=0)
        title.get_style_context().add_class("header-title")
        subtitle = Gtk.Label(
            label="Select which changes to apply. Judgment calls come after.", xalign=0
        )
        subtitle.get_style_context().add_class("header-subtitle")
        header.pack_start(title, False, False, 0)
        header.pack_start(subtitle, False, False, 0)
        self.pack_start(header, False, False, 0)

        self._rescan_notice = Gtk.Label(xalign=0)
        self._rescan_notice.get_style_context().add_class("header-subtitle")
        self._rescan_notice.set_no_show_all(True)
        self._rescan_notice.set_margin_start(14)
        self._rescan_notice.set_margin_top(6)
        self.pack_start(self._rescan_notice, False, False, 0)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(14)
        toolbar.set_margin_end(14)
        toolbar.set_margin_top(10)
        toolbar.set_margin_bottom(6)
        select_all_btn = Gtk.Button(label="Select all")
        select_all_btn.get_style_context().add_class("flat")
        select_all_btn.connect("clicked", lambda *_: self._set_all(True))
        select_none_btn = Gtk.Button(label="Select none")
        select_none_btn.get_style_context().add_class("flat")
        select_none_btn.connect("clicked", lambda *_: self._set_all(False))
        toolbar.pack_start(select_all_btn, False, False, 0)
        toolbar.pack_start(select_none_btn, False, False, 0)
        self.pack_start(toolbar, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        list_box.get_style_context().add_class("row-list")
        list_box.set_margin_start(14)
        list_box.set_margin_end(14)

        for item in classification.apt_items:
            packages = [
                pkg
                for action in item.actions
                if action.get("type") == "apt_install"
                for pkg in action["packages"]
            ]
            row = SetupRow(
                title=item.reason,
                reason=f"would install: {', '.join(packages)}",
                badge="INSTALL",
            )
            list_box.pack_start(row, False, False, 0)
            self._rows.append((row, "apt", item))

        for fixer in classification.fixers_to_run:
            row = SetupRow(title=fixer.summary, reason=f"fix id: {fixer.id}", badge="FIX")
            list_box.pack_start(row, False, False, 0)
            self._rows.append((row, "fixer", fixer))

        if not self._rows:
            empty = Gtk.Label(label="Nothing to do right now — this machine is clean.", xalign=0)
            empty.get_style_context().add_class("item-reason")
            empty.set_margin_top(20)
            list_box.pack_start(empty, False, False, 0)

        scroller.add(list_box)
        self.pack_start(scroller, True, True, 0)

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

    def _update_count(self):
        selected = sum(1 for row, _k, _p in self._rows if row.selected)
        self._count_label.set_text(f"{selected} of {len(self._rows)} selected")

    def _on_start_clicked(self, _button):
        selected = [(kind, payload) for row, kind, payload in self._rows if row.selected]
        self._on_start(selected)

    def show_rescan_notice(self):
        self._rescan_notice.set_text(
            "Done. This list reflects the last scan — re-open to pick up any new state."
        )
        self._rescan_notice.show()
