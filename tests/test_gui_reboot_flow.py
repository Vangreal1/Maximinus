"""Tests specific to the new pipeline: Judgment's OK button routes selected
items through the shared progress screen (tagged as "judgment" items)
instead of applying them inline, and the flow always ends on a reboot
recommendation screen rather than jumping straight back to setup.
"""

import time
from unittest.mock import patch

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

try:
    Gtk.init_check()
    _HAS_DISPLAY = True
except Exception:
    _HAS_DISPLAY = False

pytestmark = pytest.mark.skipif(not _HAS_DISPLAY, reason="no display available")


def _pump_until(condition, timeout_s=6):
    ctx = GLib.MainContext.default()
    deadline = time.time() + timeout_s
    while not condition():
        if time.time() > deadline:
            raise AssertionError(f"timed out waiting for {condition}")
        if ctx.pending():
            ctx.iteration(False)
        else:
            time.sleep(0.02)


def test_judgment_page_hands_selection_to_on_done_synchronously():
    from maximinus.engine import PlanItem
    from maximinus.gui.pages.judgment import JudgmentPage

    item = PlanItem(
        rule_id="luks-auto-unlock",
        reason="Encrypted (LUKS) drive detected",
        actions=[{"type": "manual_step", "description": "..."}],
        when=["fs.luks_present"],
    )
    received = {}
    page = JudgmentPage([item], on_done=lambda selected: received.setdefault("selected", selected))
    page._rows[0].check.set_active(True)
    page.ok_button.clicked()

    # No artificial delay: on_done fires immediately, synchronously.
    assert received["selected"] == [item]


def test_progress_page_describes_judgment_items():
    from maximinus.engine import PlanItem
    from maximinus.gui.pages.progress import _describe

    item = PlanItem(
        rule_id="luks-auto-unlock",
        reason="Encrypted (LUKS) drive detected",
        actions=[{"type": "manual_step", "description": "..."}],
        when=["fs.luks_present"],
    )
    headline, _detail = _describe("judgment", item)
    assert "Encrypted (LUKS) drive detected" in headline


def test_window_routes_selected_judgment_items_through_progress_tagged_correctly():
    with patch("maximinus.gui.window.collect_facts", return_value={"fs.luks_present"}):
        from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

        _load_css()
        app = MaximinusApp()
        win = MaximinusWindow(app)
        win.show_all()

        item = win.judgment_page._rows[0].item
        win._go_to_progress_for_judgment([item])

        assert win.stack.get_visible_child_name() == "progress"
        assert win.progress_page._queue == [("judgment", item)]

        win.destroy()


def test_window_reuses_progress_page_instance_for_both_passes():
    with patch("maximinus.gui.window.collect_facts", return_value={"fs.luks_present"}):
        from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

        _load_css()
        app = MaximinusApp()
        win = MaximinusWindow(app)
        win.show_all()

        first_progress_page = win.progress_page
        win.setup_page.start_button.clicked()
        assert win.progress_page is first_progress_page

        _pump_until(lambda: win.stack.get_visible_child_name() == "judgment")

        item = win.judgment_page._rows[0].item
        win._go_to_progress_for_judgment([item])
        assert win.progress_page is first_progress_page

        win.destroy()


def test_reboot_page_later_button_quits_the_app():
    with patch("maximinus.gui.window.collect_facts", return_value=set()):
        from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

        _load_css()
        app = MaximinusApp()
        win = MaximinusWindow(app)
        win.show_all()

        win._go_to_reboot([])
        assert win.stack.get_visible_child_name() == "reboot"

        with patch.object(app, "quit") as quit_mock:
            win.reboot_page.later_button.clicked()
        quit_mock.assert_called_once()

        win.destroy()
