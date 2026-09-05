"""Find mounted drives/partitions and the category folders on them that
could be pooled together (Downloads, Documents, Pictures, ...).

We only ever look for folders that already exist — we never create a
Downloads folder on a drive that doesn't have one, and we never guess at
merging folders whose structure doesn't already match.
"""

import json
import os
import subprocess

# XDG-style category folders we know how to pool. Matched case-insensitively.
CATEGORY_DIRS = ["Downloads", "Documents", "Pictures", "Videos", "Music", "Desktop"]

# Mountpoints/prefixes we never treat as poolable branches: system,
# boot, swap, and anything virtual/pseudo.
_EXCLUDED_PREFIXES = ("/boot", "/snap", "/var", "/run", "/sys", "/proc", "/dev", "/tmp")
_POOLABLE_FSTYPES = {
    "ext2",
    "ext3",
    "ext4",
    "btrfs",
    "xfs",
    "ntfs",
    "ntfs3",
    "exfat",
    "fuseblk",
}


def _findmnt_json():
    try:
        out = subprocess.run(
            ["findmnt", "-J", "-o", "TARGET,SOURCE,FSTYPE"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
        return json.loads(out) if out else {}
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        return {}


def list_mount_candidates():
    """Mountpoints of real, local, non-system partitions (candidate drives)."""
    data = _findmnt_json()
    candidates = []
    for entry in data.get("filesystems", []):
        target = entry.get("target", "")
        fstype = (entry.get("fstype") or "").lower()
        if fstype not in _POOLABLE_FSTYPES:
            continue
        if target == "/" or any(target.startswith(p) for p in _EXCLUDED_PREFIXES):
            continue
        candidates.append(target)
    home = os.path.expanduser("~")
    if home not in candidates:
        candidates.insert(0, home if os.path.ismount(home) else "/")
    return candidates


def _find_category_dir(root, category):
    """Return the path to `category` under `root` if it exists, searching a
    shallow, predictable set of likely locations — never an open-ended walk."""
    candidates = [
        os.path.join(root, category),
        os.path.join(root, category.lower()),
    ]
    # Second Mint/Ubuntu install on another partition: /mnt/x/home/<user>/Downloads
    home_dir = os.path.join(root, "home")
    if os.path.isdir(home_dir):
        try:
            for entry in os.listdir(home_dir):
                candidates.append(os.path.join(home_dir, entry, category))
        except OSError:
            pass
    for path in candidates:
        if os.path.isdir(path) and not os.path.islink(path):
            return path
    return None


def discover_category_branches():
    """Map each category folder name to the list of existing directories
    (across all detected drives) that could be merged into one pool.

    Only categories with 2+ branches are worth pooling; callers should
    filter on that.
    """
    roots = list_mount_candidates()
    result = {}
    for category in CATEGORY_DIRS:
        found = []
        for root in roots:
            path = _find_category_dir(root, category)
            if path:
                found.append(path)
        if found:
            result[category] = found
    return result
