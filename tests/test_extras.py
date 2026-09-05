from unittest.mock import mock_open, patch

from maximinus.detectors import extras


def test_tlp_missing_flagged_on_laptop_without_it():
    with patch.object(extras, "_is_laptop", return_value=True), patch.object(
        extras, "_dpkg_installed", return_value=False
    ):
        assert extras.detect_power_management_facts() == {"power.tlp_missing"}


def test_tlp_not_flagged_on_desktop():
    with patch.object(extras, "_is_laptop", return_value=False):
        assert extras.detect_power_management_facts() == set()


def test_tlp_not_flagged_when_already_installed():
    with patch.object(extras, "_is_laptop", return_value=True), patch.object(
        extras, "_dpkg_installed", return_value=True
    ):
        assert extras.detect_power_management_facts() == set()


def test_fwupd_missing_flagged():
    with patch("shutil.which", return_value=None), patch.object(
        extras, "_dpkg_installed", return_value=False
    ):
        assert extras.detect_firmware_update_facts() == {"firmware.fwupd_missing"}


def test_fwupd_not_flagged_when_binary_present():
    with patch("shutil.which", return_value="/usr/bin/fwupdmgr"):
        assert extras.detect_firmware_update_facts() == set()


def test_codecs_missing_flagged():
    with patch.object(extras, "_dpkg_installed", return_value=False):
        assert extras.detect_codec_facts() == {"media.codecs_missing"}


def test_printing_missing_flagged():
    with patch.object(extras, "_dpkg_installed", return_value=False):
        assert extras.detect_printing_facts() == {"printing.cups_missing"}


def test_low_ram_no_swap_flagged():
    with patch.object(extras, "_total_ram_kb", return_value=2 * 1024 * 1024), patch.object(
        extras, "_has_any_swap", return_value=False
    ):
        assert extras.detect_swap_facts() == {"mem.low_ram_no_swap"}


def test_low_ram_but_has_swap_not_flagged():
    with patch.object(extras, "_total_ram_kb", return_value=2 * 1024 * 1024), patch.object(
        extras, "_has_any_swap", return_value=True
    ):
        assert extras.detect_swap_facts() == set()


def test_plenty_of_ram_not_flagged_even_without_swap():
    with patch.object(extras, "_total_ram_kb", return_value=16 * 1024 * 1024), patch.object(
        extras, "_has_any_swap", return_value=False
    ):
        assert extras.detect_swap_facts() == set()


def test_has_any_swap_reads_proc_swaps():
    header_only = "Filename\t\t\t\tType\t\tSize\tUsed\tPriority\n"
    with patch("builtins.open", mock_open(read_data=header_only)):
        assert extras._has_any_swap() is False

    with_entry = header_only + "/swapfile\tfile\t2097148\t0\t-2\n"
    with patch("builtins.open", mock_open(read_data=with_entry)):
        assert extras._has_any_swap() is True
