import subprocess
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


def test_build_pool_writes_boot_safe_fstab_options(tmp_path):
    branch_a = tmp_path / "a"
    branch_b = tmp_path / "b"
    branch_a.mkdir()
    branch_b.mkdir()
    written = {}

    def fake_write_root_file(path, content, mode="0644"):
        written["path"] = path
        written["content"] = content

    successful = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch.object(pool, "is_pooled", return_value=False), patch.object(
        pool, "ensure_mergerfs_installed"
    ), patch.object(pool, "read_root_file", return_value=""), patch.object(
        pool, "write_root_file", side_effect=fake_write_root_file
    ), patch.object(
        pool, "run_privileged", return_value=successful
    ):
        pool.build_pool(str(branch_a), [str(branch_a), str(branch_b)])

    line = written["content"]
    assert "nofail" in line
    assert f"x-systemd.requires-mounts-for={branch_a}" in line
    assert f"x-systemd.requires-mounts-for={branch_b}" in line
    assert "x-systemd.device-timeout=10" in line
    assert "x-systemd.mount-timeout=10" in line


def test_check_boot_safety_flags_branch_without_fstab_entry(tmp_path):
    branch = tmp_path / "somewhere"
    branch.mkdir()

    with patch.object(pool, "read_root_file", return_value=""), patch.object(
        pool, "_underlying_mountpoint", return_value="/mnt/other"
    ):
        warnings = pool.check_boot_safety([str(branch)])

    assert len(warnings) == 1
    assert "/mnt/other" in warnings[0]


def test_check_boot_safety_ignores_branches_already_covered_by_fstab(tmp_path):
    branch = tmp_path / "somewhere"
    branch.mkdir()
    fstab = "UUID=xyz /mnt/other ext4 defaults 0 2\n"

    with patch.object(pool, "read_root_file", return_value=fstab), patch.object(
        pool, "_underlying_mountpoint", return_value="/mnt/other"
    ):
        warnings = pool.check_boot_safety([str(branch)])

    assert warnings == []


def test_build_pool_is_noop_if_already_pooled(tmp_path):
    with patch.object(pool, "is_pooled", return_value=True), patch.object(
        pool, "ensure_mergerfs_installed"
    ) as ensure_installed:
        pool.build_pool(str(tmp_path), [str(tmp_path), str(tmp_path)])
    ensure_installed.assert_not_called()


def test_build_pool_refuses_to_mount_over_something_already_mounted_there(tmp_path):
    branch_a = tmp_path / "a"
    branch_b = tmp_path / "b"
    branch_a.mkdir()
    branch_b.mkdir()

    with patch.object(pool, "is_pooled", return_value=False), patch.object(
        pool, "_is_actively_mounted", return_value=True
    ), patch.object(pool, "ensure_mergerfs_installed") as ensure_installed:
        try:
            pool.build_pool(str(branch_a), [str(branch_a), str(branch_b)])
            assert False, "expected PoolError"
        except pool.PoolError as exc:
            assert "already has something else mounted" in str(exc)
    ensure_installed.assert_not_called()


def test_is_actively_mounted_matches_exact_path_only(tmp_path):
    target = str(tmp_path)
    result_here = subprocess.CompletedProcess(args=[], returncode=0, stdout=target + "\n", stderr="")
    with patch("subprocess.run", return_value=result_here):
        assert pool._is_actively_mounted(target) is True

    result_elsewhere = subprocess.CompletedProcess(args=[], returncode=0, stdout="/\n", stderr="")
    with patch("subprocess.run", return_value=result_elsewhere):
        assert pool._is_actively_mounted(target) is False
