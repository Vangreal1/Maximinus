"""Tests for opt-in features being a separate, unchecked-by-default screen
distinct from ordinary judgment calls, regardless of Risk Taking level.
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


def test_classify_plan_separates_opt_in_features_from_judgment_calls():
    from maximinus.engine import PlanItem
    from maximinus.fixes import FIXERS
    from maximinus.planning import classify_plan

    pool_item = PlanItem(
        rule_id="storage-pool-candidate",
        reason="Multiple drives/partitions with matching folder structure detected",
        actions=[{"type": "manual_step", "description": "..."}],
        when=["storage.poolable"],
    )
    conflict_item = PlanItem(
        rule_id="gpu-conflict",
        reason="some driver conflict",
        actions=[{"type": "manual_step", "description": "..."}],
        when=["gpu.nvidia_conflicting_packages"],
    )

    classification = classify_plan([pool_item, conflict_item], FIXERS)

    assert classification.opt_in_features == [pool_item]
    assert classification.left_for_you == [conflict_item]


def test_features_screen_is_skipped_when_nothing_opt_in():
    with patch(
        "maximinus.gui.window.collect_facts",
        return_value={"gpu.nvidia_conflicting_packages"},
    ):
        from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

        _load_css()
        app = MaximinusApp()
        win = MaximinusWindow(app)
        win.show_all()

        assert win.features_page._cards == []
        win._go_to_features_or_reboot([])
        assert win.stack.get_visible_child_name() == "reboot"

        win.destroy()


def test_features_screen_shown_and_unchecked_even_at_high_risk():
    with patch(
        "maximinus.gui.window.collect_facts",
        return_value={"storage.poolable", "gpu.nvidia_conflicting_packages"},
    ):
        from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

        _load_css()
        app = MaximinusApp()
        win = MaximinusWindow(app)
        win.show_all()

        # Storage pooling must not show up in the judgment list at all.
        judgment_ids = {row.item.rule_id for row in win.judgment_page._rows}
        assert "storage-pool-candidate" not in judgment_ids
        assert "gpu-conflict" not in judgment_ids  # sanity: only real conflict item there
        assert len(win.features_page._cards) == 1

        win.setup_page.risk_combo.set_active_id("High")
        win._go_to_features_or_reboot([])

        assert win.stack.get_visible_child_name() == "features"
        # Unlike judgment calls, opt-in features stay unchecked even at High.
        assert not any(card.selected for card in win.features_page._cards)

        win.destroy()


def test_enabling_a_feature_routes_through_progress_to_reboot_screen():
    with patch("subprocess.run", side_effect=AssertionError("no real commands in this test")):
        with patch(
            "maximinus.gui.window.collect_facts", return_value={"storage.poolable"}
        ), patch("maximinus.gui.window.list_luks_devices", return_value=[]):
            from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

            _load_css()
            app = MaximinusApp()
            win = MaximinusWindow(app)
            win.show_all()

            win._go_to_features_or_reboot([])
            assert win.stack.get_visible_child_name() == "features"

            win.features_page._cards[0].check.set_active(True)
            win.features_page.enable_button.clicked()

            # Enabling now routes through the shared progress screen
            # (a third pass, same as setup and judgment items) rather
            # than applying inline on the features screen itself.
            assert win.stack.get_visible_child_name() == "progress"
            assert win.progress_page._queue == [("feature", win.features_page._cards[0].item)]

            _pump_until(lambda: win.stack.get_visible_child_name() == "reboot")
            win.destroy()


def test_skip_button_goes_to_reboot_screen_without_enabling():
    with patch("maximinus.gui.window.collect_facts", return_value={"storage.poolable"}):
        from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

        _load_css()
        app = MaximinusApp()
        win = MaximinusWindow(app)
        win.show_all()

        win._go_to_features_or_reboot([])
        win.features_page.skip_button.clicked()

        assert win.stack.get_visible_child_name() == "reboot"
        win.destroy()
