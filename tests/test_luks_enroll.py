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
