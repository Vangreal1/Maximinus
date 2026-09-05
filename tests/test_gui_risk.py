"""Tests for the Risk Taking dropdown: it should only change which rows
start checked, never what's offered, and the choice made on the setup
screen should carry over to whether judgment-call rows start checked too.
"""

from unittest.mock import patch

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


def test_setup_row_default_matrix():
    from maximinus.gui import risk

    assert risk.setup_row_default("apt", "Never") is False
    assert risk.setup_row_default("fixer", "Never") is False

    assert risk.setup_row_default("apt", "Low") is True
    assert risk.setup_row_default("fixer", "Low") is False

    assert risk.setup_row_default("apt", "Medium") is True
    assert risk.setup_row_default("fixer", "Medium") is True

    assert risk.setup_row_default("apt", "High") is True
    assert risk.setup_row_default("fixer", "High") is True


def test_judgment_default_only_true_for_high():
    from maximinus.gui import risk

    assert risk.judgment_default("Never") is False
    assert risk.judgment_default("Low") is False
    assert risk.judgment_default("Medium") is False
    assert risk.judgment_default("High") is True


def _build_setup_page():
    from maximinus.engine import PlanItem
    from maximinus.gui.pages.setup import SetupPage
    from maximinus.planning import Classification

    apt_item = PlanItem(
        rule_id="exfat-support",
        reason="exFAT-formatted drive/partition detected",
        actions=[{"type": "apt_install", "packages": ["exfatprogs"]}],
        when=["fs.exfat_present"],
    )
    fixer_item = PlanItem(
        rule_id="time-sync-disabled",
        reason="NTP time synchronization is disabled",
        actions=[{"type": "manual_step", "description": "..."}],
        when=["time.ntp_disabled"],
    )

    class FakeFixer:
        id = "time-sync-disabled"
        fact = "time.ntp_disabled"
        summary = "Enable NTP time sync."

    classification = Classification(
        apt_items=[apt_item],
        packages=["exfatprogs"],
        fixers_to_run=[FakeFixer()],
        fixer_items=[fixer_item],
        left_for_you=[],
    )
    return SetupPage(classification, on_start=lambda *_: None)


def test_default_risk_level_is_medium_and_both_rows_checked():
    page = _build_setup_page()
    assert page.get_risk_level() == "Medium"
    assert all(row.selected for row, _kind, _payload in page._rows)


def test_switching_to_never_unchecks_everything():
    page = _build_setup_page()
    page.risk_combo.set_active_id("Never")
    assert page.get_risk_level() == "Never"
    assert not any(row.selected for row, _kind, _payload in page._rows)


def test_switching_to_low_checks_only_apt_rows():
    page = _build_setup_page()
    page.risk_combo.set_active_id("Low")
    by_kind = {kind: row.selected for row, kind, _payload in page._rows}
    assert by_kind["apt"] is True
    assert by_kind["fixer"] is False


def test_manual_toggle_survives_until_risk_level_changes_again():
    # Changing the dropdown resets defaults; toggling a row by hand between
    # dropdown changes should stick until the next dropdown change.
    page = _build_setup_page()
    row, _kind, _payload = page._rows[0]
    row.check.set_active(False)
    assert not row.selected
    # no dropdown change happened, so the manual toggle should still hold
    assert not row.selected


def test_window_carries_risk_level_from_setup_to_judgment():
    with patch("subprocess.run", side_effect=AssertionError("no real commands in this test")):
        with patch(
            "maximinus.gui.window.collect_facts",
            return_value={"fs.exfat_present", "fs.luks_present"},
        ):
            from maximinus.gui.window import MaximinusApp, MaximinusWindow, _load_css

            _load_css()
            app = MaximinusApp()
            win = MaximinusWindow(app)
            win.show_all()

            win.setup_page.risk_combo.set_active_id("High")
            win.setup_page.start_button.clicked()  # -> progress, captures risk level
            win._go_to_judgment()  # simulate progress finishing

            assert all(row.selected for row in win.judgment_page._rows)
            win.destroy()
