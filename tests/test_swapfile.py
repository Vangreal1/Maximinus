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

    # install(create), chattr, fallocate, mkswap, swapon
    with patch("os.path.exists", return_value=False), patch.object(
        swapfile, "read_root_file", return_value=""
    ), patch.object(swapfile, "write_root_file", side_effect=fake_write), patch.object(
        swapfile, "run_privileged", return_value=_ok()
    ) as run:
        swapfile.apply()

    assert run.call_count == 5
    assert "/swapfile none swap sw,nofail 0 0" in written["content"]


def test_falls_back_to_dd_when_fallocate_is_refused():
    # e.g. a btrfs copy-on-write file rejecting fallocate for swap.
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == "fallocate":
            return _fail("Operation not supported")
        return _ok()

    with patch("os.path.exists", return_value=False), patch.object(
        swapfile, "read_root_file", return_value=""
    ), patch.object(swapfile, "write_root_file"), patch.object(
        swapfile, "run_privileged", side_effect=fake_run
    ):
        swapfile.apply()

    commands = [cmd[0] for cmd in calls]
    assert "fallocate" in commands
    assert "dd" in commands
    assert commands.index("dd") > commands.index("fallocate")


def test_raises_if_both_fallocate_and_dd_fail():
    with patch("os.path.exists", return_value=False), patch.object(
        swapfile, "read_root_file", return_value=""
    ), patch.object(swapfile, "run_privileged") as run:

        def fake_run(cmd, **kwargs):
            if cmd[0] == "install":
                return _ok()
            if cmd[0] == "chattr":
                return _ok()
            return _fail(f"{cmd[0]} failed")

        run.side_effect = fake_run
        try:
            swapfile.apply()
            assert False, "expected FixError"
        except FixError as exc:
            assert "fallocate failed" in str(exc)
            assert "dd fallback also failed" in str(exc)


def test_chattr_failure_does_not_abort_the_whole_fixer():
    # chattr +C failing (e.g. not supported on this filesystem) must be
    # a harmless no-op, not a fatal error.
    def fake_run(cmd, **kwargs):
        if cmd[0] == "chattr":
            return _fail("chattr: not supported")
        return _ok()

    with patch("os.path.exists", return_value=False), patch.object(
        swapfile, "read_root_file", return_value=""
    ), patch.object(swapfile, "write_root_file"), patch.object(
        swapfile, "run_privileged", side_effect=fake_run
    ):
        swapfile.apply()  # should not raise


def test_mkswap_failure_raises_fixerror():
    def fake_run(cmd, **kwargs):
        if cmd[0] == "mkswap":
            return _fail("mkswap: bad")
        return _ok()

    with patch("os.path.exists", return_value=False), patch.object(
        swapfile, "read_root_file", return_value=""
    ), patch.object(swapfile, "run_privileged", side_effect=fake_run):
        try:
            swapfile.apply()
            assert False, "expected FixError"
        except FixError as exc:
            assert "mkswap" in str(exc)
