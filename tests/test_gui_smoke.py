"""Minimal GUI smoke tests. Skipped where GTK/PyGObject or a display isn't
available (e.g. a headless CI box) rather than failing the whole suite.

The show_all() check exists because of a real bug found during manual
testing: MaximinusApp.do_activate() called win.present() without
win.show_all() first, which left every child widget invisible — the
window rendered as a blank pane with nothing in it, no error raised.
"""

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

try:
    Gtk.init_check()
    _HAS_DISPLAY = True
except Exception:
    _HAS_DISPLAY = False

pytestmark = pytest.mark.skipif(not _HAS_DISPLAY, reason="no display available")


def test_planning_module_does_not_import_gi():
    # planning.py must not import gi — the CLI depends on it and shouldn't
    # require GTK to be installed.
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path("maximinus/planning.py").read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    assert "gi" not in modules


def test_window_widgets_are_visible_after_show_all():
    # Regression guard for a real bug found during manual testing:
    # MaximinusApp.do_activate() called win.present() without
    # win.show_all() first. present() alone does not recursively show
    # child widgets, so the window rendered as a blank pane — every widget
    # existed but none of them were shown, and nothing raised an error.
    # (Exercising do_activate() itself isn't reliable outside a real
    # app.run() loop — GApplication needs its startup signal emitted first
    # — so this checks the same show_all()-then-present() sequence directly.)
    from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

    _load_css()
    app = MaximinusApp()
    win = MaximinusWindow(app)
    assert not win.setup_page.get_visible()  # not shown yet — sanity check

    win.show_all()
    win.present()

    assert win.get_visible()
    assert win.stack.get_visible()
    assert win.setup_page.get_visible()
    assert win.setup_page.start_button.get_visible()

    win.destroy()


def test_setup_page_selection_and_start_callback(tmp_path):
    from maximinus.engine import PlanItem
    from maximinus.gui.pages.setup import SetupPage
    from maximinus.planning import Classification

    item = PlanItem(
        rule_id="exfat-support",
        reason="exFAT-formatted drive/partition detected",
        actions=[{"type": "apt_install", "packages": ["exfatprogs"]}],
        when=["fs.exfat_present"],
    )
    classification = Classification(apt_items=[item], packages=["exfatprogs"], fixers_to_run=[], left_for_you=[])

    captured = {}

    def on_start(selected):
        captured["selected"] = selected

    page = SetupPage(classification, on_start=on_start)
    assert len(page._rows) == 1

    page._rows[0][0].check.set_active(False)
    page.start_button.clicked()
    assert captured["selected"] == []

    page._rows[0][0].check.set_active(True)
    page.start_button.clicked()
    assert len(captured["selected"]) == 1
    assert captured["selected"][0][0] == "apt"
