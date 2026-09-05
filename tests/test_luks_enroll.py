import subprocess
from unittest.mock import patch

from maximinus.security import luks_enroll


def test_enroll_is_a_noop_if_already_enrolled():
    with patch.object(luks_enroll, "get_uuid", return_value="abc-123"), patch.object(
        luks_enroll, "already_enrolled", return_value=True
    ), patch("subprocess.run") as run:
        uuid = luks_enroll.enroll("/dev/sda3", passphrase="unused")

    assert uuid == "abc-123"
    run.assert_not_called()


def test_keyfile_size_is_random_key_material_not_a_passphrase():
    import os

    key_bytes = os.urandom(luks_enroll.KEYFILE_SIZE)
    assert len(key_bytes) == luks_enroll.KEYFILE_SIZE


def test_already_enrolled_requires_both_keyfile_and_crypttab_entry():
    # keyfile present, crypttab missing -> NOT fully enrolled (a prior run
    # was interrupted, or the user removed the crypttab line by hand).
    with patch.object(luks_enroll, "keyfile_exists", return_value=True), patch.object(
        luks_enroll, "crypttab_registered", return_value=False
    ):
        assert luks_enroll.already_enrolled("uuid-1") is False

    with patch.object(luks_enroll, "keyfile_exists", return_value=True), patch.object(
        luks_enroll, "crypttab_registered", return_value=True
    ):
        assert luks_enroll.already_enrolled("uuid-1") is True


def test_enroll_resumes_a_half_finished_run_without_asking_for_passphrase_again():
    # Keyfile already exists (from a prior interrupted run) but crypttab
    # was never updated. enroll() should finish the job using the existing
    # keyfile rather than prompting for the passphrase again or generating
    # a redundant new keyfile.
    with patch.object(luks_enroll, "get_uuid", return_value="uuid-1"), patch.object(
        luks_enroll, "already_enrolled", return_value=False
    ), patch.object(luks_enroll, "keyfile_exists", return_value=True), patch.object(
        luks_enroll, "_register_crypttab"
    ) as register, patch("subprocess.run") as run, patch(
        "getpass.getpass"
    ) as getpass_mock:
        result = luks_enroll.enroll("/dev/sda3")

    assert result == "uuid-1"
    register.assert_called_once()
    getpass_mock.assert_not_called()
    run.assert_not_called()  # no cryptsetup luksAddKey, no mkdir/install


def _ok(stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def _fail(stderr="No key available with this passphrase."):
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def test_unlock_device_is_a_noop_if_already_unlocked():
    with patch.object(luks_enroll, "get_uuid", return_value="uuid-1"), patch(
        "os.path.exists", return_value=True
    ), patch("subprocess.run") as run:
        path = luks_enroll.unlock_device("/dev/sda3", "unused")

    assert path == "/dev/mapper/maximinus-uuid-1"
    run.assert_not_called()


def test_unlock_device_calls_cryptsetup_open_with_passphrase_on_stdin():
    with patch.object(luks_enroll, "get_uuid", return_value="abc12345"), patch(
        "os.path.exists", return_value=False
    ), patch("subprocess.run", return_value=_ok()) as run:
        path = luks_enroll.unlock_device("/dev/sda3", "correct-passphrase")

    assert path == "/dev/mapper/maximinus-abc12345"
    run.assert_called_once()
    args, kwargs = run.call_args
    assert args[0] == ["sudo", "cryptsetup", "open", "/dev/sda3", "maximinus-abc12345"]
    assert kwargs["input"] == "correct-passphrase\n"


def test_unlock_device_raises_enrollment_error_on_wrong_passphrase():
    with patch.object(luks_enroll, "get_uuid", return_value="abc12345"), patch(
        "os.path.exists", return_value=False
    ), patch("subprocess.run", return_value=_fail()):
        try:
            luks_enroll.unlock_device("/dev/sda3", "wrong-passphrase")
            assert False, "expected EnrollmentError"
        except luks_enroll.EnrollmentError as exc:
            assert "No key available" in str(exc)


def test_unlock_device_never_returns_or_leaks_the_passphrase():
    # The passphrase must never appear in the returned value or be
    # retrievable from the function's return — only the mapper path comes
    # back.
    with patch.object(luks_enroll, "get_uuid", return_value="abc12345"), patch(
        "os.path.exists", return_value=False
    ), patch("subprocess.run", return_value=_ok()):
        path = luks_enroll.unlock_device("/dev/sda3", "super-secret-passphrase")

    assert "super-secret-passphrase" not in path
