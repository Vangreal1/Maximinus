"""Regression tests: a failed root-file write must surface as the calling
module's own error type (EnrollmentError/PoolError/FixError), never as a
raw subprocess.CalledProcessError or TypeError leaking out of run_privileged.

This class of bug was previously invisible because every other test mocked
write_root_file/run_privileged directly instead of exercising the real
failure path through them.
"""

import subprocess
from unittest.mock import patch

from maximinus.fixes import grub_dualboot
from maximinus.security import luks_enroll as le
from maximinus.security.sudo_session import run_privileged
from maximinus.storage import pool


def _failed(stderr="permission denied"):
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def _ok():
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def test_run_privileged_accepts_explicit_check_false():
    # This used to raise TypeError: got multiple values for keyword 'check'.
    with patch("subprocess.run", return_value=_ok()) as run:
        result = run_privileged(["true"], check=False)
    assert result.returncode == 0
    assert run.call_args.kwargs["check"] is False


def test_run_privileged_defaults_to_check_true():
    with patch("subprocess.run", return_value=_ok()) as run:
        run_privileged(["true"])
    assert run.call_args.kwargs["check"] is True


def test_enroll_mkdir_failure_raises_enrollment_error_not_calledprocesserror():
    with patch.object(le, "get_uuid", return_value="uuid-1"), patch.object(
        le, "already_enrolled", return_value=False
    ), patch.object(le, "keyfile_exists", return_value=False), patch(
        "subprocess.run",
        side_effect=[
            _ok(),  # cryptsetup luksAddKey
            _failed("mkdir: permission denied"),  # mkdir KEY_DIR
        ],
    ):
        try:
            le.enroll("/dev/fake", passphrase="pw")
            assert False, "expected EnrollmentError"
        except le.EnrollmentError as exc:
            assert "permission denied" in str(exc)


def test_pool_fstab_write_failure_raises_poolerror(tmp_path):
    branch_a = tmp_path / "a"
    branch_b = tmp_path / "b"
    branch_a.mkdir()
    branch_b.mkdir()

    with patch.object(pool, "is_pooled", return_value=False), patch.object(
        pool, "ensure_mergerfs_installed"
    ), patch.object(pool, "read_root_file", return_value=""), patch(
        "subprocess.run", return_value=_failed("install: permission denied")
    ):
        try:
            pool.build_pool(str(branch_a), [str(branch_a), str(branch_b)])
            assert False, "expected PoolError"
        except pool.PoolError as exc:
            assert "permission denied" in str(exc)


def test_grub_dualboot_write_failure_raises_fixerror():
    with patch.object(grub_dualboot, "read_root_file", return_value=""), patch(
        "subprocess.run",
        side_effect=[
            _ok(),  # apt-get install os-prober
            _failed("install: permission denied"),  # write /etc/default/grub
        ],
    ):
        try:
            grub_dualboot.apply()
            assert False, "expected FixError"
        except grub_dualboot.FixError as exc:
            assert "permission denied" in str(exc)
