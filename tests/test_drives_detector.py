from unittest.mock import patch

from maximinus.detectors import drives


def _lsblk(devices):
    return {"blockdevices": devices}


def test_list_encrypted_devices_finds_luks_and_bitlocker():
    fake_lsblk = _lsblk(
        [
            {"name": "sda3", "fstype": "crypto_LUKS", "mountpoint": None},
            {"name": "sdb2", "fstype": "BitLocker", "mountpoint": None},
            {"name": "sdc1", "fstype": "ext4", "mountpoint": "/"},
        ]
    )
    with patch.object(drives, "_lsblk_json", return_value=fake_lsblk):
        result = drives.list_encrypted_devices()

    assert set(result) == {("/dev/sda3", "luks"), ("/dev/sdb2", "bitlocker")}


def test_list_luks_devices_excludes_bitlocker():
    fake_lsblk = _lsblk(
        [
            {"name": "sda3", "fstype": "crypto_LUKS", "mountpoint": None},
            {"name": "sdb2", "fstype": "BitLocker", "mountpoint": None},
        ]
    )
    with patch.object(drives, "_lsblk_json", return_value=fake_lsblk):
        result = drives.list_luks_devices()

    assert result == ["/dev/sda3"]


def test_list_encrypted_devices_empty_when_none_found():
    fake_lsblk = _lsblk([{"name": "sda1", "fstype": "ext4", "mountpoint": "/"}])
    with patch.object(drives, "_lsblk_json", return_value=fake_lsblk):
        assert drives.list_encrypted_devices() == []


def test_bitlocker_fact_detected():
    fake_lsblk = _lsblk([{"name": "sdb2", "fstype": "BitLocker", "mountpoint": None}])
    with patch.object(drives, "_lsblk_json", return_value=fake_lsblk):
        facts = drives.detect_drive_facts()

    assert "fs.bitlocker_present" in facts


def test_encrypted_devices_found_in_nested_partitions():
    fake_lsblk = _lsblk(
        [
            {
                "name": "sda",
                "fstype": None,
                "mountpoint": None,
                "children": [{"name": "sda3", "fstype": "crypto_LUKS", "mountpoint": None}],
            }
        ]
    )
    with patch.object(drives, "_lsblk_json", return_value=fake_lsblk):
        result = drives.list_encrypted_devices()

    assert result == [("/dev/sda3", "luks")]
