"""Progress screen: status text above a progress bar, plus a log of steps
already finished.

This is not wired to real execution yet. Each step is simulated with a
short delay via GLib.timeout_add instead of actually calling apt-get or
fixer.apply(). See the module docstring in maximinus/gui/__init__.py for
why. Swapping in real execution later only means replacing what _step()
does; the screen, the sequencing, and the callback contract all stay the
same.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

STEP_DELAY_MS = 550


def _describe(kind, payload):
    """Return (headline, detail) for the status text. headline is the
    short line always shown; detail explains why this step is happening,
    in plain terms, and can be blank."""
    if kind == "apt":
        packages = [
            pkg
            for action in payload.actions
            if action.get("type") == "apt_install"
            for pkg in action["packages"]
        ]
        return f"Installing {', '.join(packages)}", f"Reason: {payload.reason}."
    return f"Fixing: {payload.summary}", ""


class ProgressPage(Gtk.Box):
    def __init__(self, on_finished):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_finished = on_finished
        self._queue = []
        self._index = 0
        self._timeout_id = None

        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        header.get_style_context().add_class("header")
        title = Gtk.Label(label="MAXIMINUS", xalign=0)
        title.get_style_context().add_class("header-title")
        subtitle = Gtk.Label(
            label="Working through the selected changes. Nothing real is happening yet, this is a preview.",
            xalign=0,
        )
        subtitle.get_style_context().add_class("header-subtitle")
        header.pack_start(title, False, False, 0)
        header.pack_start(subtitle, False, False, 0)
        self.pack_start(header, False, False, 0)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        body.set_margin_start(14)
        body.set_margin_end(14)
        body.set_margin_top(16)
        body.set_margin_bottom(14)

        self.status_label = Gtk.Label(label="Getting ready.", xalign=0)
        self.status_label.get_style_context().add_class("status-text")
        self.status_label.set_line_wrap(True)
        body.pack_start(self.status_label, False, False, 0)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        body.pack_start(self.progress_bar, False, False, 0)

        log_frame = Gtk.ScrolledWindow()
        log_frame.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        log_frame.get_style_context().add_class("panel")
        self.log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.log_box.set_margin_start(8)
        self.log_box.set_margin_end(8)
        self.log_box.set_margin_top(6)
        self.log_box.set_margin_bottom(6)
        log_frame.add(self.log_box)
        body.pack_start(log_frame, True, True, 0)

        self.pack_start(body, True, True, 0)

    def start(self, selected_items):
        self._queue = selected_items
        self._index = 0
        for child in self.log_box.get_children():
            self.log_box.remove(child)
        self.progress_bar.set_fraction(0.0)

        if not self._queue:
            self.status_label.set_text("Nothing was selected, so there's nothing to do here.")
            GLib.timeout_add(STEP_DELAY_MS, self._finish)
            return

        self.status_label.set_text("Starting.")
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
        self._timeout_id = GLib.timeout_add(STEP_DELAY_MS, self._step)

    def _log(self, text):
        label = Gtk.Label(label=f"done: {text}", xalign=0)
        label.get_style_context().add_class("log-text")
        label.set_line_wrap(True)
        self.log_box.pack_start(label, False, False, 0)
        label.show()

    def _step(self):
        kind, payload = self._queue[self._index]
        headline, detail = _describe(kind, payload)
        self.status_label.set_text(f"{headline}\n{detail}" if detail else headline)

        self._index += 1
        self.progress_bar.set_fraction(self._index / len(self._queue))
        self._log(headline)

        if self._index >= len(self._queue):
            self._timeout_id = GLib.timeout_add(STEP_DELAY_MS, self._finish)
            return False
        return True

    def _finish(self):
        self.status_label.set_text("That's everything that was selected.")
        self.progress_bar.set_fraction(1.0)
        self._on_finished()
        return False
