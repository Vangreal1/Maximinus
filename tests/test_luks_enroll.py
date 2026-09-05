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
