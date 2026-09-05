"""Tests for the catch-all error display: an unexpected exception during a
running step must show up as visible text on screen (styled via the
error-text CSS class, i.e. the red text) instead of freezing the screen or
just printing a traceback to the terminal.
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


def test_format_error_verbosity_levels():
    from maximinus.gui.errors import format_error

    exc = ValueError("bad value")

    level1 = format_error(exc, "doing a thing", verbosity=1)
    assert "ValueError" not in level1
    assert "doing a thing" in level1

    level2 = format_error(exc, "doing a thing", verbosity=2)
    assert "ValueError" in level2
    assert "bad value" in level2
    assert "Traceback" not in level2

    try:
        raise exc
    except ValueError as raised:
        level3 = format_error(raised, "doing a thing", verbosity=3)
    assert "Traceback" in level3


def test_default_verbosity_is_two():
    from maximinus.gui.errors import DEFAULT_VERBOSITY

    assert DEFAULT_VERBOSITY == 2


def test_progress_page_shows_red_error_on_unexpected_exception():
    from maximinus.gui.pages.progress import ProgressPage

    page = ProgressPage(on_finished=lambda: None)

    class BrokenPayload:
        pass

    with patch("maximinus.gui.pages.progress._describe", side_effect=RuntimeError("boom")):
        page.start([("apt", BrokenPayload())])
        _pump_until(lambda: page.error_label.get_visible())

    assert "RuntimeError" in page.error_label.get_text()
    assert "boom" in page.error_label.get_text()
    assert page.continue_button.get_visible()
    assert "error-text" in page.error_label.get_style_context().list_classes()


def test_progress_page_continue_button_proceeds_past_the_error():
    from maximinus.gui.pages.progress import ProgressPage

    finished = {"called": False}

    def on_finished():
        finished["called"] = True

    page = ProgressPage(on_finished=on_finished)

    class BrokenPayload:
        pass

    with patch("maximinus.gui.pages.progress._describe", side_effect=RuntimeError("boom")):
        page.start([("apt", BrokenPayload())])
        _pump_until(lambda: page.continue_button.get_visible())

    page.continue_button.clicked()
    assert finished["called"]


def test_progress_page_normal_run_never_shows_error():
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
    assert not page.error_label.get_visible()
    assert not page.continue_button.get_visible()


def test_judgment_page_shows_error_text_class_on_unexpected_exception():
    from maximinus.engine import PlanItem
    from maximinus.gui.pages.judgment import JudgmentPage

    item = PlanItem(
        rule_id="luks-auto-unlock",
        reason="Encrypted (LUKS) drive detected",
        actions=[{"type": "manual_step", "description": "..."}],
        when=["fs.luks_present"],
    )
    page = JudgmentPage([item], on_done=lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    page._rows[0].check.set_active(True)
    page.ok_button.clicked()

    _pump_until(lambda: "error-text" in page.status_label.get_style_context().list_classes())
    assert "RuntimeError" in page.status_label.get_text()
    assert page.ok_button.get_sensitive()  # not left stuck disabled


def test_features_page_shows_error_text_class_on_unexpected_exception():
    from maximinus.engine import PlanItem
    from maximinus.gui.pages.features import FeaturesPage

    item = PlanItem(
        rule_id="storage-pool-candidate",
        reason="Multiple drives with matching folders",
        actions=[{"type": "manual_step", "description": "..."}],
        when=["storage.poolable"],
    )
    page = FeaturesPage([item], on_done=lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    page._cards[0].check.set_active(True)
    page.enable_button.clicked()

    _pump_until(lambda: "error-text" in page.status_label.get_style_context().list_classes())
    assert "RuntimeError" in page.status_label.get_text()
    assert page.enable_button.get_sensitive()
