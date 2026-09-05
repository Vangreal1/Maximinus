"""Tests for the Reboot screen's real action: a confirmation dialog gates
an actual `systemctl reboot` call. Every test here mocks trigger_reboot
(or asserts subprocess.run is never called for real) — this is the one
place in the whole GUI where a bug in the test itself could actually
reboot the machine running the suite, so the guard is load-bearing, not
decorative.
"""

import subprocess
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


def _ok():
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def _fail(stderr="boom"):
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def test_clicking_reboot_never_calls_trigger_reboot_directly():
    # Clicking the button only opens the confirmation dialog; the actual
    # reboot call happens solely from the dialog's response handler.
    from maximinus.gui.pages.reboot import RebootPage

    with patch("maximinus.gui.pages.reboot.trigger_reboot") as trigger:
        page = RebootPage(on_later=lambda: None)
        page.reboot_button.clicked()

    trigger.assert_not_called()


def test_cancelling_the_confirmation_dialog_does_not_reboot():
    from maximinus.gui.pages.reboot import RebootPage

    with patch("maximinus.gui.pages.reboot.trigger_reboot") as trigger:
        page = RebootPage(on_later=lambda: None)

        class FakeDialog:
            def destroy(self):
                pass

        page._on_confirm_response(FakeDialog(), Gtk.ResponseType.CANCEL)

    trigger.assert_not_called()


def test_confirming_the_dialog_calls_trigger_reboot_exactly_once():
    from maximinus.gui.pages.reboot import RebootPage

    with patch("maximinus.gui.pages.reboot.trigger_reboot", return_value=_ok()) as trigger:
        page = RebootPage(on_later=lambda: None)

        class FakeDialog:
            def destroy(self):
                pass

        page._on_confirm_response(FakeDialog(), Gtk.ResponseType.OK)

    trigger.assert_called_once()
    assert not page.error_label.get_visible()


def test_reboot_command_failure_shows_error_text():
    from maximinus.gui.pages.reboot import RebootPage

    with patch(
        "maximinus.gui.pages.reboot.trigger_reboot",
        return_value=_fail("Failed to reboot: access denied"),
    ):
        page = RebootPage(on_later=lambda: None)

        class FakeDialog:
            def destroy(self):
                pass

        page._on_confirm_response(FakeDialog(), Gtk.ResponseType.OK)

    assert page.error_label.get_visible()
    assert "access denied" in page.error_label.get_text()


def test_reboot_raising_an_exception_shows_error_not_a_crash():
    from maximinus.gui.pages.reboot import RebootPage

    with patch(
        "maximinus.gui.pages.reboot.trigger_reboot", side_effect=FileNotFoundError("no systemctl")
    ):
        page = RebootPage(on_later=lambda: None)

        class FakeDialog:
            def destroy(self):
                pass

        page._on_confirm_response(FakeDialog(), Gtk.ResponseType.OK)

    assert page.error_label.get_visible()
    assert "FileNotFoundError" in page.error_label.get_text()


def test_later_button_calls_on_later_and_never_touches_reboot():
    from maximinus.gui.pages.reboot import RebootPage

    later_called = {"value": False}
    with patch("maximinus.gui.pages.reboot.trigger_reboot") as trigger:
        page = RebootPage(on_later=lambda: later_called.__setitem__("value", True))
        page.later_button.clicked()

    assert later_called["value"]
    trigger.assert_not_called()


def test_trigger_reboot_calls_systemctl_reboot_with_no_sudo():
    # Confirms trigger_reboot's own implementation shape without ever
    # actually invoking it for real: subprocess.run itself is mocked.
    from maximinus.gui.pages.reboot import trigger_reboot

    with patch("subprocess.run", return_value=_ok()) as run:
        trigger_reboot()

    run.assert_called_once()
    args = run.call_args.args[0]
    assert args == ["systemctl", "reboot"]
    assert "sudo" not in args
