"""Tests for the progress screen's structured report: each step logs a
type badge, its headline, and an elapsed-time stamp, and a finished run
appends a one-line summary — not just a bare scrolling line of text.
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


def _row_texts(log_box):
    """Flatten each log row's child labels' text, for easy substring checks."""
    texts = []
    for row in log_box.get_children():
        if isinstance(row, Gtk.Box):
            texts.append(" ".join(child.get_text() for child in row.get_children()))
        else:
            texts.append(row.get_text())
    return texts


def test_each_step_logs_a_kind_badge_and_headline():
    from maximinus.engine import PlanItem
    from maximinus.gui.pages.progress import ProgressPage

    apt_item = PlanItem(
        rule_id="exfat-support",
        reason="exFAT-formatted drive/partition detected",
        actions=[{"type": "apt_install", "packages": ["exfatprogs"]}],
        when=["fs.exfat_present"],
    )
    page = ProgressPage(on_finished=lambda: None)
    page.start([("apt", apt_item)])

    _pump_until(lambda: len(page.log_box.get_children()) >= 1)

    texts = _row_texts(page.log_box)
    assert any("INSTALL" in t and "Installing exfatprogs" in t for t in texts)


def test_log_row_includes_an_elapsed_timestamp():
    from maximinus.engine import PlanItem
    from maximinus.gui.pages.progress import ProgressPage

    item = PlanItem(
        rule_id="exfat-support",
        reason="exFAT-formatted drive/partition detected",
        actions=[{"type": "apt_install", "packages": ["exfatprogs"]}],
        when=["fs.exfat_present"],
    )
    page = ProgressPage(on_finished=lambda: None)
    page.start([("apt", item)])

    _pump_until(lambda: len(page.log_box.get_children()) >= 1)

    texts = _row_texts(page.log_box)
    assert any(t.strip().endswith("s") and "+" in t for t in texts)


def test_progress_bar_shows_step_counter():
    from maximinus.engine import PlanItem
    from maximinus.gui.pages.progress import ProgressPage

    items = [
        (
            "apt",
            PlanItem(
                rule_id=f"item-{i}",
                reason=f"reason {i}",
                actions=[{"type": "apt_install", "packages": [f"pkg{i}"]}],
                when=[f"fact.{i}"],
            ),
        )
        for i in range(3)
    ]
    page = ProgressPage(on_finished=lambda: None)
    page.start(items)

    _pump_until(lambda: page.progress_bar.get_text() is not None and "Step 1" in page.progress_bar.get_text())
    assert page.progress_bar.get_text() == "Step 1 of 3"


def test_finished_run_appends_a_summary_line():
    from maximinus.engine import PlanItem
    from maximinus.gui.pages.progress import ProgressPage

    item = PlanItem(
        rule_id="exfat-support",
        reason="exFAT-formatted drive/partition detected",
        actions=[{"type": "apt_install", "packages": ["exfatprogs"]}],
        when=["fs.exfat_present"],
    )
    finished = {"called": False}
    page = ProgressPage(on_finished=lambda: finished.__setitem__("called", True))
    page.start([("apt", item)])

    _pump_until(lambda: finished["called"])

    texts = _row_texts(page.log_box)
    assert any("Summary" in t and "1 of 1" in t for t in texts)
    assert "done" in page.progress_bar.get_text()


def test_failed_step_logs_a_failed_row_in_red():
    from maximinus.gui.pages.progress import ProgressPage

    class BrokenPayload:
        pass

    with patch("maximinus.gui.pages.progress._describe", side_effect=RuntimeError("boom")):
        page = ProgressPage(on_finished=lambda: None)
        page.start([("apt", BrokenPayload())])
        _pump_until(lambda: page.error_label.get_visible())

    texts = _row_texts(page.log_box)
    assert any("FAILED" in t for t in texts)


def test_new_start_clears_the_previous_reports_rows():
    from maximinus.engine import PlanItem
    from maximinus.gui.pages.progress import ProgressPage

    item = PlanItem(
        rule_id="exfat-support",
        reason="exFAT-formatted drive/partition detected",
        actions=[{"type": "apt_install", "packages": ["exfatprogs"]}],
        when=["fs.exfat_present"],
    )
    finished = {"count": 0}
    page = ProgressPage(on_finished=lambda: finished.__setitem__("count", finished["count"] + 1))
    page.start([("apt", item)])
    _pump_until(lambda: finished["count"] == 1)

    page.start([])  # second pass, nothing selected
    _pump_until(lambda: finished["count"] == 2)

    # the "Nothing was selected" run shouldn't carry over the first run's report rows
    texts = _row_texts(page.log_box)
    assert not any("exfatprogs" in t for t in texts)
