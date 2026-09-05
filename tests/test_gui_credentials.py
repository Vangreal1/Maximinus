"""Tests for the first screen: sudo password verified once (mocked here,
never a real sudo call), and each LUKS passphrase used once to actually
unlock its drive (also mocked — never a real cryptsetup call) rather than
stored anywhere, including in the Session object.
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


def test_luks_passphrases_unlock_drives_and_are_never_stored():
    from maximinus.gui.session import Session

    session = Session()
    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=True
    ), patch("maximinus.gui.pages.credentials.unlock_device") as unlock:
        page = _make_page(["/dev/sda3", "/dev/sdb1"], session)
        page.sudo_entry.set_text("correct-password")
        page._luks_entries["/dev/sda3"].set_text("passphrase-one")
        page._luks_entries["/dev/sdb1"].set_text("passphrase-two")
        page.continue_button.clicked()

    unlock.assert_any_call("/dev/sda3", "passphrase-one")
    unlock.assert_any_call("/dev/sdb1", "passphrase-two")
    # the drives are tracked as unlocked, but nowhere is the passphrase itself kept
    assert session.unlocked_devices == {"/dev/sda3", "/dev/sdb1"}
    assert not hasattr(session, "luks_passphrases")
    # cleared from the widgets once read
    assert page._luks_entries["/dev/sda3"].get_text() == ""
    assert page._luks_entries["/dev/sdb1"].get_text() == ""


def test_wrong_luks_passphrase_shows_error_and_does_not_continue():
    from maximinus.gui.session import Session
    from maximinus.security.luks_enroll import EnrollmentError

    continued = {"called": False}
    session = Session()
    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=True
    ), patch(
        "maximinus.gui.pages.credentials.unlock_device",
        side_effect=EnrollmentError("could not unlock /dev/sda3: No key available with this passphrase."),
    ) as unlock:
        page = _make_page(["/dev/sda3"], session, on_continue=lambda: continued.__setitem__("called", True))
        page.sudo_entry.set_text("correct-password")
        page._luks_entries["/dev/sda3"].set_text("wrong-passphrase")
        page.continue_button.clicked()

    unlock.assert_called_once_with("/dev/sda3", "wrong-passphrase")
    assert not continued["called"]
    assert page.error_label.get_visible()
    assert "No key available" in page.error_label.get_text()
    assert session.unlocked_devices == set()
    assert page._luks_entries["/dev/sda3"].get_text() == ""


def test_empty_luks_passphrase_shows_error_without_calling_unlock():
    from maximinus.gui.session import Session

    session = Session()
    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=True
    ), patch("maximinus.gui.pages.credentials.unlock_device") as unlock:
        page = _make_page(["/dev/sda3"], session)
        page.sudo_entry.set_text("correct-password")
        page.continue_button.clicked()

    unlock.assert_not_called()
    assert page.error_label.get_visible()
    assert "/dev/sda3" in page.error_label.get_text()


def test_already_unlocked_device_is_not_reattempted():
    from maximinus.gui.session import Session

    session = Session()
    session.unlocked_devices.add("/dev/sda3")
    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=True
    ), patch("maximinus.gui.pages.credentials.unlock_device") as unlock:
        page = _make_page(["/dev/sda3"], session)
        page.sudo_entry.set_text("correct-password")
        page.continue_button.clicked()

    unlock.assert_not_called()


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
    session.unlocked_devices.add("/dev/sda3")
    session.clear()

    assert session.sudo_authenticated is False
    assert session.unlocked_devices == set()


def test_session_never_has_a_place_to_put_a_passphrase():
    # Guards against a future regression re-adding passphrase storage.
    from maximinus.gui.session import Session

    session = Session()
    assert not hasattr(session, "luks_passphrases")
    assert not hasattr(session, "set_luks_passphrase")
