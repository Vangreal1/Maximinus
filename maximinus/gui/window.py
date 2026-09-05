"""Main window: a Gtk.Stack cycling through Setup -> Progress -> Judgment."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from ..detectors import collect_facts
from ..engine import build_plan
from ..fixes import FIXERS
from ..planning import classify_plan
from .pages.judgment import JudgmentPage
from .pages.progress import ProgressPage
from .pages.setup import SetupPage

CSS_PATH = __file__.rsplit("/", 1)[0] + "/theme.css"


def _load_css():
    provider = Gtk.CssProvider()
    provider.load_from_path(CSS_PATH)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


class MaximinusWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Maximinus")
        self.set_default_size(720, 560)
        self.get_style_context().add_class("root-bg")

        self._facts = collect_facts()
        self._plan = build_plan(self._facts)
        self._classification = classify_plan(self._plan, FIXERS)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(150)
        self.add(self.stack)

        self.setup_page = SetupPage(self._classification, on_start=self._go_to_progress)
        self.progress_page = ProgressPage(on_finished=self._go_to_judgment)
        self.judgment_page = JudgmentPage(
            self._classification.left_for_you, on_done=self._go_to_done
        )

        self.stack.add_named(self.setup_page, "setup")
        self.stack.add_named(self.progress_page, "progress")
        self.stack.add_named(self.judgment_page, "judgment")

        self.stack.set_visible_child_name("setup")

    def _go_to_progress(self, selected_items):
        self.progress_page.start(selected_items)
        self.stack.set_visible_child_name("progress")

    def _go_to_judgment(self):
        self.stack.set_visible_child_name("judgment")

    def _go_to_done(self, _applied_items):
        self.stack.set_visible_child_name("setup")
        self.setup_page.show_rescan_notice()


class MaximinusApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.maximinus.gui", flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        _load_css()
        win = self.props.active_window
        if not win:
            win = MaximinusWindow(self)
        win.show_all()
        win.present()


def run():
    app = MaximinusApp()
    return app.run(None)
