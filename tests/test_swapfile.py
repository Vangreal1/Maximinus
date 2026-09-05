import subprocess
from unittest.mock import patch

from maximinus.fixes import swapfile
from maximinus.fixes.errors import FixError


def _ok():
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def _fail(stderr="boom"):
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def test_noop_if_swapfile_already_exists():
    with patch("os.path.exists", return_value=True), patch.object(
        swapfile, "run_privileged"
    ) as run:
        swapfile.apply()
    run.assert_not_called()


def test_noop_if_fstab_already_references_swapfile():
    with patch("os.path.exists", return_value=False), patch.object(
        swapfile, "read_root_file", return_value="/swapfile none swap sw,nofail 0 0\n"
    ), patch.object(swapfile, "run_privileged") as run:
        swapfile.apply()
    run.assert_not_called()


def test_full_success_path_writes_fstab_line():
    written = {}

    def fake_write(path, content, mode="0644"):
        written["content"] = content

    with patch("os.path.exists", return_value=False), patch.object(
        swapfile, "read_root_file", return_value=""
    ), patch.object(swapfile, "write_root_file", side_effect=fake_write), patch.object(
        swapfile, "run_privileged", return_value=_ok()
    ) as run:
        swapfile.apply()

    assert run.call_count == 4  # fallocate, chmod, mkswap, swapon
    assert "/swapfile none swap sw,nofail 0 0" in written["content"]


def test_fallocate_failure_raises_fixerror_and_stops_early():
    with patch("os.path.exists", return_value=False), patch.object(
        swapfile, "read_root_file", return_value=""
    ), patch.object(swapfile, "run_privileged", return_value=_fail("no space")) as run:
        try:
            swapfile.apply()
            assert False, "expected FixError"
        except FixError as exc:
            assert "no space" in str(exc)
    run.assert_called_once()  # never got to chmod/mkswap/swapon


def test_mkswap_failure_raises_fixerror():
    results = [_ok(), _ok(), _fail("mkswap: bad")]
    with patch("os.path.exists", return_value=False), patch.object(
        swapfile, "read_root_file", return_value=""
    ), patch.object(swapfile, "run_privileged", side_effect=results):
        try:
            swapfile.apply()
            assert False, "expected FixError"
        except FixError as exc:
            assert "mkswap" in str(exc)
