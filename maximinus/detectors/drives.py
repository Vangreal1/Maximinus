"""Drive/filesystem detection via lsblk.

Facts produced:
  fs.ntfs_present
  fs.exfat_present
  fs.hfsplus_present
  fs.other_linux_present   (a second ext4/btrfs root-like partition)
"""

import json
import shutil
import subprocess

_INTERESTING_FS = {
    "ntfs": "fs.ntfs_present",
    "ntfs3": "fs.ntfs_present",
    "exfat": "fs.exfat_present",
    "hfsplus": "fs.hfsplus_present",
    "crypto_luks": "fs.luks_present",
}


def _lsblk_json():
    if shutil.which("lsblk") is None:
        return {}
    try:
        out = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,FSTYPE,MOUNTPOINT"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
        return json.loads(out) if out else {}
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        return {}


def _walk(devices):
    for dev in devices:
        yield dev
        yield from _walk(dev.get("children", []) or [])


def detect_drive_facts():
    facts = set()
    data = _lsblk_json()
    for dev in _walk(data.get("blockdevices", [])):
        fstype = (dev.get("fstype") or "").lower()
        if fstype in _INTERESTING_FS:
            facts.add(_INTERESTING_FS[fstype])
    return facts


def list_luks_devices():
    """Return /dev paths (e.g. /dev/sda3) of LUKS-encrypted partitions."""
    data = _lsblk_json()
    devices = []
    for dev in _walk(data.get("blockdevices", [])):
        if (dev.get("fstype") or "").lower() == "crypto_luks":
            devices.append(f"/dev/{dev['name']}")
    return devices
