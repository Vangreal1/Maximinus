"""Tests for the first screen: sudo password verified once (mocked here,
never a real sudo call), LUKS passphrases collected into the in-memory
Session and never left sitting in the entry widgets afterward.
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


def _make_page(devices, session, on_continue=None):
    from maximinus.gui.pages.credentials import CredentialsPage

    return CredentialsPage(devices, session, on_continue=on_continue or (lambda: None))


def test_password_entries_mask_input():
    from maximinus.gui.session import Session

    page = _make_page(["/dev/sda3"], Session())
    assert page.sudo_entry.get_visibility() is False
    assert page._luks_entries["/dev/sda3"].get_visibility() is False


def test_no_devices_shows_placeholder_and_no_entries():
    from maximinus.gui.session import Session

    page = _make_page([], Session())
    assert page._luks_entries == {}


def test_empty_sudo_password_shows_error_without_calling_sudo():
    from maximinus.gui.session import Session

    with patch("maximinus.gui.pages.credentials.authenticate_with_password") as auth:
        page = _make_page([], Session())
        page.continue_button.clicked()

    auth.assert_not_called()
    assert page.error_label.get_visible()
    assert "sudo password" in page.error_label.get_text().lower()


def test_wrong_password_shows_error_and_does_not_continue():
    from maximinus.gui.session import Session

    continued = {"called": False}
    session = Session()
    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=False
    ) as auth:
        page = _make_page([], session, on_continue=lambda: continued.__setitem__("called", True))
        page.sudo_entry.set_text("wrong-password")
        page.continue_button.clicked()

    auth.assert_called_once_with("wrong-password")
    assert not continued["called"]
    assert page.error_label.get_visible()
    assert not session.sudo_authenticated
    # the password is never left sitting in the field either way
    assert page.sudo_entry.get_text() == ""


def test_correct_password_authenticates_and_continues():
    from maximinus.gui.session import Session

    continued = {"called": False}
    session = Session()
    with patch("maximinus.gui.pages.credentials.authenticate_with_password", return_value=True):
        page = _make_page([], session, on_continue=lambda: continued.__setitem__("called", True))
        page.sudo_entry.set_text("correct-password")
        page.continue_button.clicked()

    assert continued["called"]
    assert session.sudo_authenticated
    assert page.sudo_entry.get_text() == ""


def test_luks_passphrases_collected_into_session_and_cleared_from_entries():
    from maximinus.gui.session import Session

    session = Session()
    with patch("maximinus.gui.pages.credentials.authenticate_with_password", return_value=True):
        page = _make_page(["/dev/sda3", "/dev/sdb1"], session)
        page.sudo_entry.set_text("correct-password")
        page._luks_entries["/dev/sda3"].set_text("passphrase-one")
        page._luks_entries["/dev/sdb1"].set_text("passphrase-two")
        page.continue_button.clicked()

    assert session.luks_passphrases == {
        "/dev/sda3": "passphrase-one",
        "/dev/sdb1": "passphrase-two",
    }
    # cleared from the widgets once captured
    assert page._luks_entries["/dev/sda3"].get_text() == ""
    assert page._luks_entries["/dev/sdb1"].get_text() == ""


def test_unexpected_exception_during_auth_shows_error_not_a_crash():
    from maximinus.gui.session import Session

    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password",
        side_effect=RuntimeError("boom"),
    ):
        page = _make_page([], Session())
        page.sudo_entry.set_text("whatever")
        page.continue_button.clicked()

    assert page.error_label.get_visible()
    assert "RuntimeError" in page.error_label.get_text()
    assert page.continue_button.get_sensitive()


def test_session_clear_wipes_everything():
    from maximinus.gui.session import Session

    session = Session()
    session.sudo_authenticated = True
    session.set_luks_passphrase("/dev/sda3", "secret")
    session.clear()

    assert session.sudo_authenticated is False
    assert session.luks_passphrases == {}
