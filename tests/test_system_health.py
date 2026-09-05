from unittest.mock import patch

from maximinus.detectors import system_health as sh


def test_apt_broken_state_detected_when_audit_has_output():
    with patch.object(sh, "_run", return_value="pkgname is in a not-fully-installed state\n"):
        assert sh._detect_apt_broken_state() == {"apt.broken_state"}


def test_apt_healthy_when_audit_is_empty():
    with patch.object(sh, "_run", return_value=""):
        assert sh._detect_apt_broken_state() == set()


def test_dkms_headers_missing_when_modules_present_and_headers_absent():
    with patch.object(sh, "_run", return_value="nvidia, 535.129.03, 6.5.0-generic: installed\n"), \
         patch.object(sh, "_dpkg_installed", return_value=False), \
         patch("shutil.which", return_value="/usr/sbin/dkms"):
        assert sh._detect_dkms_headers_missing() == {"dkms.headers_missing"}


def test_dkms_headers_ok_when_headers_installed():
    with patch.object(sh, "_run", return_value="nvidia, 535.129.03, 6.5.0-generic: installed\n"), \
         patch.object(sh, "_dpkg_installed", return_value=True), \
         patch("shutil.which", return_value="/usr/sbin/dkms"):
        assert sh._detect_dkms_headers_missing() == set()


def test_dkms_headers_ok_when_no_dkms_modules_registered():
    with patch.object(sh, "_run", return_value=""), patch("shutil.which", return_value="/usr/sbin/dkms"):
        assert sh._detect_dkms_headers_missing() == set()


def test_time_sync_disabled_detected():
    with patch.object(sh, "_run", return_value="no\n"), patch("shutil.which", return_value="/usr/bin/timedatectl"):
        assert sh._detect_time_sync_disabled() == {"time.ntp_disabled"}


def test_time_sync_enabled_produces_no_fact():
    with patch.object(sh, "_run", return_value="yes\n"), patch("shutil.which", return_value="/usr/bin/timedatectl"):
        assert sh._detect_time_sync_disabled() == set()


def test_grub_os_prober_flagged_when_ntfs_present_and_prober_missing():
    with patch.object(sh, "detect_drive_facts", return_value={"fs.ntfs_present"}), \
         patch("shutil.which", return_value=None), \
         patch.object(sh, "_read_file", return_value=""):
        assert sh._detect_grub_os_prober_issue() == {"grub.os_prober_disabled_with_other_os"}


def test_grub_os_prober_flagged_when_explicitly_disabled_in_config():
    with patch.object(sh, "detect_drive_facts", return_value={"fs.ntfs_present"}), \
         patch("shutil.which", return_value="/usr/bin/os-prober"), \
         patch.object(sh, "_read_file", return_value="GRUB_DISABLE_OS_PROBER=true\n"):
        assert sh._detect_grub_os_prober_issue() == {"grub.os_prober_disabled_with_other_os"}


def test_grub_os_prober_ok_when_installed_and_enabled():
    with patch.object(sh, "detect_drive_facts", return_value={"fs.ntfs_present"}), \
         patch("shutil.which", return_value="/usr/bin/os-prober"), \
         patch.object(sh, "_read_file", return_value="GRUB_DISABLE_OS_PROBER=false\n"):
        assert sh._detect_grub_os_prober_issue() == set()


def test_grub_os_prober_not_flagged_without_ntfs_signal():
    with patch.object(sh, "detect_drive_facts", return_value=set()):
        assert sh._detect_grub_os_prober_issue() == set()


def test_audio_conflict_detected_when_both_installed():
    with patch.object(sh, "_dpkg_installed", side_effect=lambda pkg: pkg in {"pulseaudio", "pipewire-pulse"}):
        assert sh._detect_audio_conflict() == {"audio.pulseaudio_pipewire_conflict"}


def test_audio_conflict_absent_when_only_one_installed():
    with patch.object(sh, "_dpkg_installed", side_effect=lambda pkg: pkg == "pipewire-pulse"):
        assert sh._detect_audio_conflict() == set()


def test_ufw_inactive_detected():
    with patch("shutil.which", return_value="/usr/sbin/ufw"), patch.object(
        sh, "_run", return_value="Status: inactive\n"
    ):
        assert sh._detect_ufw_inactive() == {"firewall.ufw_inactive"}


def test_ufw_active_produces_no_fact():
    with patch("shutil.which", return_value="/usr/sbin/ufw"), patch.object(
        sh, "_run", return_value="Status: active\n"
    ):
        assert sh._detect_ufw_inactive() == set()
