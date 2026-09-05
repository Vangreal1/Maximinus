"""Main window: a Gtk.Stack cycling through
Credentials -> Setup -> Progress -> Judgment -> Progress -> Features
-> Progress -> Reboot.

The three Progress visits share one ProgressPage instance: one pass per
screen that hands it a selection (setup, then judgment, then opt-in
features), each with its own on_finished callback passed to
ProgressPage.start() so the same screen can continue on to a different
place each time.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

from ..detectors import collect_facts
from ..detectors.drives import list_encrypted_devices
from ..engine import build_plan
from ..fixes import FIXERS
from ..planning import classify_plan
from .pages.credentials import CredentialsPage
from .pages.features import FeaturesPage
from .pages.judgment import JudgmentPage
from .pages.progress import ProgressPage
from .pages.reboot import RebootPage
from .pages.setup import SetupPage
from .session import Session

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
        self.set_default_size(540, 420)
        self.get_style_context().add_class("root-bg")

        self._facts = collect_facts()
        self._plan = build_plan(self._facts)
        self._classification = classify_plan(self._plan, FIXERS)
        self._session = Session()

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(150)
        self.add(self.stack)

        self.credentials_page = CredentialsPage(
            list_encrypted_devices(), self._session, on_continue=self._go_to_setup
        )
        self.setup_page = SetupPage(self._classification, on_start=self._go_to_progress)
        self.progress_page = ProgressPage(on_finished=self._go_to_judgment)
        self.judgment_page = JudgmentPage(
            self._classification.left_for_you, on_done=self._go_to_progress_for_judgment
        )
        # Opt-in features (e.g. storage pooling) are never pre-checked, at
        # any Risk Taking level: turning one on changes ongoing behavior,
        # not a one-off condition, so it always needs its own explicit
        # decision on its own screen, separate from both setup and
        # judgment calls. See maximinus/planning.py's OPT_IN_FEATURE_FACTS.
        self.features_page = FeaturesPage(
            self._classification.opt_in_features, on_done=self._go_to_progress_for_features
        )
        self.reboot_page = RebootPage(on_later=self._quit)

        self.stack.add_named(self.credentials_page, "credentials")
        self.stack.add_named(self.setup_page, "setup")
        self.stack.add_named(self.progress_page, "progress")
        self.stack.add_named(self.judgment_page, "judgment")
        self.stack.add_named(self.features_page, "features")
        self.stack.add_named(self.reboot_page, "reboot")

        self.stack.set_visible_child_name("credentials")
        self._risk_level = self.setup_page.get_risk_level()

    def _go_to_setup(self):
        self.stack.set_visible_child_name("setup")

    def _go_to_progress(self, selected_items):
        """First pass: the safe/automatic items chosen on the setup screen."""
        self._risk_level = self.setup_page.get_risk_level()
        self.progress_page.start(selected_items, on_finished=self._go_to_judgment)
        self.stack.set_visible_child_name("progress")

    def _go_to_judgment(self):
        self.judgment_page.apply_risk_default(self._risk_level)
        self.stack.set_visible_child_name("judgment")

    def _go_to_progress_for_judgment(self, selected_items):
        """Second pass: whichever judgment-call items the user opted into.
        Reuses the same progress screen as the first pass; if nothing was
        selected there's nothing to show a progress bar for, so this skips
        straight to the opt-in features screen (or past it, if there are
        none)."""
        if not selected_items:
            self._go_to_features_or_reboot([])
            return
        tagged = [("judgment", item) for item in selected_items]
        self.progress_page.start(tagged, on_finished=lambda: self._go_to_features_or_reboot([]))
        self.stack.set_visible_child_name("progress")

    def _go_to_features_or_reboot(self, _applied_items):
        if self._classification.opt_in_features:
            self.stack.set_visible_child_name("features")
        else:
            self._go_to_reboot([])

    def _go_to_progress_for_features(self, selected_items):
        """Third pass: whichever opt-in features the user turned on."""
        if not selected_items:
            self._go_to_reboot([])
            return
        tagged = [("feature", item) for item in selected_items]
        self.progress_page.start(tagged, on_finished=lambda: self._go_to_reboot([]))
        self.stack.set_visible_child_name("progress")

    def _go_to_reboot(self, _applied_items):
        self.stack.set_visible_child_name("reboot")

    def _quit(self):
        app = self.get_application()
        if app is not None:
            app.quit()
        else:
            self.destroy()


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
