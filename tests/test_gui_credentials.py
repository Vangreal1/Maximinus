"""Tests for the first screen: sudo password verified once (mocked here,
never a real sudo call), and each drive secret (LUKS passphrase or
BitLocker password/recovery key) used once to actually unlock its drive
(also mocked — never a real cryptsetup/dislocker call) rather than stored
anywhere, including in the Session object. Rejections show up under the
specific field that failed, not as one shared banner.
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

    page = _make_page([("/dev/sda3", "luks")], Session())
    assert page.sudo_entry.get_visibility() is False
    assert page._drive_rows["/dev/sda3"].entry.get_visibility() is False


def test_no_devices_shows_placeholder_and_no_rows():
    from maximinus.gui.session import Session

    page = _make_page([], Session())
    assert page._drive_rows == {}


def test_drive_row_label_mentions_drive_type():
    from maximinus.gui.session import Session

    page = _make_page([("/dev/sda3", "luks"), ("/dev/sdb2", "bitlocker")], Session())
    assert page._drive_rows["/dev/sda3"].kind == "luks"
    assert page._drive_rows["/dev/sdb2"].kind == "bitlocker"


def test_empty_sudo_password_shows_error_under_sudo_field_without_calling_sudo():
    from maximinus.gui.session import Session

    with patch("maximinus.gui.pages.credentials.authenticate_with_password") as auth:
        page = _make_page([], Session())
        page.continue_button.clicked()

    auth.assert_not_called()
    assert page.sudo_error_label.get_visible()
    assert "sudo password" in page.sudo_error_label.get_text().lower()


def test_wrong_password_shows_error_under_sudo_field_and_does_not_continue():
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
    assert page.sudo_error_label.get_visible()
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
    assert not page.sudo_error_label.get_visible()


def test_luks_passphrases_unlock_drives_and_are_never_stored():
    from maximinus.gui.session import Session

    session = Session()
    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=True
    ), patch("maximinus.gui.pages.credentials.unlock_luks") as unlock:
        page = _make_page([("/dev/sda3", "luks"), ("/dev/sdb1", "luks")], session)
        page.sudo_entry.set_text("correct-password")
        page._drive_rows["/dev/sda3"].entry.set_text("passphrase-one")
        page._drive_rows["/dev/sdb1"].entry.set_text("passphrase-two")
        page.continue_button.clicked()

    unlock.assert_any_call("/dev/sda3", "passphrase-one")
    unlock.assert_any_call("/dev/sdb1", "passphrase-two")
    # the drives are tracked as unlocked, but nowhere is the passphrase itself kept
    assert session.unlocked_devices == {"/dev/sda3", "/dev/sdb1"}
    assert not hasattr(session, "luks_passphrases")
    # cleared from the widgets once read
    assert page._drive_rows["/dev/sda3"].entry.get_text() == ""
    assert page._drive_rows["/dev/sdb1"].entry.get_text() == ""


def test_bitlocker_secret_unlocks_drive_via_bitlocker_module():
    from maximinus.gui.session import Session

    session = Session()
    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=True
    ), patch("maximinus.gui.pages.credentials.bitlocker.unlock_device") as unlock:
        page = _make_page([("/dev/sdb2", "bitlocker")], session)
        page.sudo_entry.set_text("correct-password")
        page._drive_rows["/dev/sdb2"].entry.set_text("123456-123456-123456-123456-123456-123456-123456-123456")
        page.continue_button.clicked()

    unlock.assert_called_once_with(
        "/dev/sdb2", "123456-123456-123456-123456-123456-123456-123456-123456"
    )
    assert session.unlocked_devices == {"/dev/sdb2"}


def test_wrong_drive_secret_shows_error_under_that_drives_field_only():
    from maximinus.gui.session import Session
    from maximinus.security.luks_enroll import EnrollmentError

    continued = {"called": False}
    session = Session()
    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=True
    ), patch(
        "maximinus.gui.pages.credentials.unlock_luks",
        side_effect=EnrollmentError("could not unlock /dev/sda3: No key available with this passphrase."),
    ) as unlock:
        page = _make_page(
            [("/dev/sda3", "luks")], session, on_continue=lambda: continued.__setitem__("called", True)
        )
        page.sudo_entry.set_text("correct-password")
        page._drive_rows["/dev/sda3"].entry.set_text("wrong-passphrase")
        page.continue_button.clicked()

    unlock.assert_called_once_with("/dev/sda3", "wrong-passphrase")
    assert not continued["called"]
    row = page._drive_rows["/dev/sda3"]
    assert row.error_label.get_visible()
    assert "No key available" in row.error_label.get_text()
    # the sudo field's own error area is untouched by a drive-specific failure
    assert not page.sudo_error_label.get_visible()
    assert session.unlocked_devices == set()
    assert row.entry.get_text() == ""


def test_wrong_secret_on_one_drive_does_not_show_error_on_a_different_drive():
    from maximinus.gui.session import Session
    from maximinus.security.luks_enroll import EnrollmentError

    session = Session()

    def fake_unlock(device, secret):
        if device == "/dev/sda3":
            raise EnrollmentError("could not unlock /dev/sda3: wrong passphrase")

    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=True
    ), patch("maximinus.gui.pages.credentials.unlock_luks", side_effect=fake_unlock):
        page = _make_page([("/dev/sda3", "luks"), ("/dev/sdb1", "luks")], session)
        page.sudo_entry.set_text("correct-password")
        page._drive_rows["/dev/sda3"].entry.set_text("wrong")
        page._drive_rows["/dev/sdb1"].entry.set_text("also-not-tried-yet")
        page.continue_button.clicked()

    assert page._drive_rows["/dev/sda3"].error_label.get_visible()
    assert not page._drive_rows["/dev/sdb1"].error_label.get_visible()


def test_empty_drive_secret_shows_error_without_calling_unlock():
    from maximinus.gui.session import Session

    session = Session()
    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=True
    ), patch("maximinus.gui.pages.credentials.unlock_luks") as unlock:
        page = _make_page([("/dev/sda3", "luks")], session)
        page.sudo_entry.set_text("correct-password")
        page.continue_button.clicked()

    unlock.assert_not_called()
    assert page._drive_rows["/dev/sda3"].error_label.get_visible()


def test_already_unlocked_device_is_not_reattempted():
    from maximinus.gui.session import Session

    session = Session()
    session.unlocked_devices.add("/dev/sda3")
    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=True
    ), patch("maximinus.gui.pages.credentials.unlock_luks") as unlock:
        page = _make_page([("/dev/sda3", "luks")], session)
        page.sudo_entry.set_text("correct-password")
        page.continue_button.clicked()

    unlock.assert_not_called()


def test_unexpected_exception_during_sudo_check_shows_error_not_a_crash():
    from maximinus.gui.session import Session

    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password",
        side_effect=RuntimeError("boom"),
    ):
        page = _make_page([], Session())
        page.sudo_entry.set_text("whatever")
        page.continue_button.clicked()

    assert page.sudo_error_label.get_visible()
    assert "RuntimeError" in page.sudo_error_label.get_text()
    assert page.continue_button.get_sensitive()


def test_unexpected_exception_during_unlock_shows_error_under_that_drive():
    from maximinus.gui.session import Session

    with patch(
        "maximinus.gui.pages.credentials.authenticate_with_password", return_value=True
    ), patch("maximinus.gui.pages.credentials.unlock_luks", side_effect=RuntimeError("boom")):
        page = _make_page([("/dev/sda3", "luks")], Session())
        page.sudo_entry.set_text("correct-password")
        page._drive_rows["/dev/sda3"].entry.set_text("whatever")
        page.continue_button.clicked()

    row = page._drive_rows["/dev/sda3"]
    assert row.error_label.get_visible()
    assert "RuntimeError" in row.error_label.get_text()
    assert page.continue_button.get_sensitive()


def test_session_clear_wipes_everything():
    from maximinus.gui.session import Session

    session = Session()
    session.sudo_authenticated = True
    session.unlocked_devices.add("/dev/sda3")
    session.clear()

    assert session.sudo_authenticated is False
    assert session.unlocked_devices == set()


def test_session_never_has_a_place_to_put_a_secret():
    # Guards against a future regression re-adding secret storage.
    from maximinus.gui.session import Session

    session = Session()
    assert not hasattr(session, "luks_passphrases")
    assert not hasattr(session, "set_luks_passphrase")
