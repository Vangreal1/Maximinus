import subprocess
from unittest.mock import patch

from maximinus.security import bitlocker


def _ok():
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def _fail(stderr="Cannot decrypt the VMK with this user password."):
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def test_looks_like_recovery_key_matches_valid_format():
    key = "123456-123456-123456-123456-123456-123456-123456-123456"
    assert bitlocker._looks_like_recovery_key(key) is True


def test_looks_like_recovery_key_rejects_a_plain_password():
    assert bitlocker._looks_like_recovery_key("MyPassword123!") is False
    assert bitlocker._looks_like_recovery_key("123456-123456") is False  # too short


def test_unlock_device_uses_dash_p_for_a_recovery_key():
    key = "123456-123456-123456-123456-123456-123456-123456-123456"
    with patch.object(bitlocker, "is_unlocked", return_value=False), patch.object(
        bitlocker, "ensure_dislocker_installed"
    ), patch.object(bitlocker, "run_privileged", return_value=_ok()), patch(
        "subprocess.run", return_value=_ok()
    ) as run:
        bitlocker.unlock_device("/dev/sdb2", key)

    args = run.call_args.args[0]
    assert any(arg.startswith("-p") for arg in args)
    assert not any(arg.startswith("-u") for arg in args)


def test_unlock_device_uses_dash_u_for_a_password():
    with patch.object(bitlocker, "is_unlocked", return_value=False), patch.object(
        bitlocker, "ensure_dislocker_installed"
    ), patch.object(bitlocker, "run_privileged", return_value=_ok()), patch(
        "subprocess.run", return_value=_ok()
    ) as run:
        bitlocker.unlock_device("/dev/sdb2", "MyPassword123!")

    args = run.call_args.args[0]
    assert any(arg.startswith("-u") for arg in args)
    assert not any(arg.startswith("-p") for arg in args)


def test_unlock_device_is_a_noop_if_already_unlocked():
    with patch.object(bitlocker, "is_unlocked", return_value=True), patch.object(
        bitlocker, "run_privileged"
    ) as run_priv, patch("subprocess.run") as run:
        path = bitlocker.unlock_device("/dev/sdb2", "unused")

    assert path == bitlocker.mountpoint_for("/dev/sdb2")
    run_priv.assert_not_called()
    run.assert_not_called()


def test_unlock_device_raises_on_wrong_secret():
    with patch.object(bitlocker, "is_unlocked", return_value=False), patch.object(
        bitlocker, "ensure_dislocker_installed"
    ), patch.object(bitlocker, "run_privileged", return_value=_ok()), patch(
        "subprocess.run", return_value=_fail()
    ):
        try:
            bitlocker.unlock_device("/dev/sdb2", "wrong-password")
            assert False, "expected UnlockError"
        except bitlocker.UnlockError as exc:
            assert "Cannot decrypt the VMK" in str(exc)


def test_unlock_device_never_leaks_the_secret_in_the_return_value():
    with patch.object(bitlocker, "is_unlocked", return_value=False), patch.object(
        bitlocker, "ensure_dislocker_installed"
    ), patch.object(bitlocker, "run_privileged", return_value=_ok()), patch(
        "subprocess.run", return_value=_ok()
    ):
        path = bitlocker.unlock_device("/dev/sdb2", "super-secret-password")

    assert "super-secret-password" not in path


def test_mkdir_failure_raises_unlock_error():
    with patch.object(bitlocker, "is_unlocked", return_value=False), patch.object(
        bitlocker, "ensure_dislocker_installed"
    ), patch.object(bitlocker, "run_privileged", return_value=_fail("mkdir: permission denied")):
        try:
            bitlocker.unlock_device("/dev/sdb2", "whatever")
            assert False, "expected UnlockError"
        except bitlocker.UnlockError as exc:
            assert "permission denied" in str(exc)
