import subprocess
from unittest.mock import patch

from maximinus.fixes import FIXERS, FixError
from maximinus.fixes import apt_repair, timesync


def test_registry_has_all_expected_fixers():
    assert set(FIXERS) == {
        "apt-broken-state",
        "dkms-headers-missing",
        "time-sync-disabled",
        "grub-os-prober-disabled",
        "low-memory-no-swap",
    }


def _ok():
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def _fail():
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")


def test_apt_repair_succeeds_when_both_steps_succeed():
    with patch.object(apt_repair, "run_privileged", return_value=_ok()) as run:
        apt_repair.apply()
    assert run.call_count == 2


def test_apt_repair_raises_fixerror_on_failure():
    with patch.object(apt_repair, "run_privileged", return_value=_fail()):
        try:
            apt_repair.apply()
            assert False, "expected FixError"
        except FixError:
            pass


def test_timesync_raises_fixerror_on_failure():
    with patch.object(timesync, "run_privileged", return_value=_fail()):
        try:
            timesync.apply()
            assert False, "expected FixError"
        except FixError:
            pass


def test_timesync_succeeds():
    with patch.object(timesync, "run_privileged", return_value=_ok()) as run:
        timesync.apply()
    run.assert_called_once()
