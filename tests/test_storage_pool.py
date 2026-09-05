import os
from unittest.mock import patch

from maximinus.storage import discovery, pool


def test_find_category_dir_only_matches_existing_dirs(tmp_path):
    root = tmp_path / "driveA"
    (root / "Downloads").mkdir(parents=True)
    assert discovery._find_category_dir(str(root), "Downloads") == str(root / "Downloads")
    assert discovery._find_category_dir(str(root), "Documents") is None


def test_discover_category_branches_only_reports_multi_branch_categories(tmp_path):
    drive_a = tmp_path / "a"
    drive_b = tmp_path / "b"
    (drive_a / "Downloads").mkdir(parents=True)
    (drive_b / "Downloads").mkdir(parents=True)
    (drive_a / "Documents").mkdir(parents=True)  # only on one drive

    with patch.object(discovery, "list_mount_candidates", return_value=[str(drive_a), str(drive_b)]):
        result = discovery.discover_category_branches()

    assert result["Downloads"] == [str(drive_a / "Downloads"), str(drive_b / "Downloads")]
    assert result["Documents"] == [str(drive_a / "Documents")]


def test_build_pool_rejects_single_branch(tmp_path):
    with patch.object(pool, "is_pooled", return_value=False):
        try:
            pool.build_pool(str(tmp_path), [str(tmp_path)])
            assert False, "expected PoolError"
        except pool.PoolError:
            pass


def test_build_pool_is_noop_if_already_pooled(tmp_path):
    with patch.object(pool, "is_pooled", return_value=True), patch.object(
        pool, "ensure_mergerfs_installed"
    ) as ensure_installed:
        pool.build_pool(str(tmp_path), [str(tmp_path), str(tmp_path)])
    ensure_installed.assert_not_called()
