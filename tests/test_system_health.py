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
    with patch("os.path.isdir", return_value=True), \
         patch.object(sh, "detect_drive_facts", return_value={"fs.ntfs_present"}), \
         patch("shutil.which", return_value=None), \
         patch.object(sh, "_read_file", return_value=""):
        assert sh._detect_grub_os_prober_issue() == {"grub.os_prober_disabled_with_other_os"}


def test_grub_os_prober_flagged_when_explicitly_disabled_in_config():
    with patch("os.path.isdir", return_value=True), \
         patch.object(sh, "detect_drive_facts", return_value={"fs.ntfs_present"}), \
         patch("shutil.which", return_value="/usr/bin/os-prober"), \
         patch.object(sh, "_read_file", return_value="GRUB_DISABLE_OS_PROBER=true\n"):
        assert sh._detect_grub_os_prober_issue() == {"grub.os_prober_disabled_with_other_os"}


def test_grub_os_prober_ok_when_installed_and_enabled():
    with patch("os.path.isdir", return_value=True), \
         patch.object(sh, "detect_drive_facts", return_value={"fs.ntfs_present"}), \
         patch("shutil.which", return_value="/usr/bin/os-prober"), \
         patch.object(sh, "_read_file", return_value="GRUB_DISABLE_OS_PROBER=false\n"):
        assert sh._detect_grub_os_prober_issue() == set()


def test_grub_os_prober_not_flagged_without_any_other_os_signal():
    with patch("os.path.isdir", return_value=True), \
         patch.object(sh, "detect_drive_facts", return_value=set()), patch.object(
        sh, "_other_os_efi_entries", return_value=set()
    ):
        assert sh._detect_grub_os_prober_issue() == set()


def test_grub_os_prober_flagged_by_second_linux_install_efi_entry():
    with patch("os.path.isdir", return_value=True), \
         patch.object(sh, "detect_drive_facts", return_value=set()), \
         patch.object(sh, "_other_os_efi_entries", return_value={"fedora"}), \
         patch("shutil.which", return_value=None):
        assert sh._detect_grub_os_prober_issue() == {"grub.os_prober_disabled_with_other_os"}


def test_grub_os_prober_not_flagged_when_not_using_grub_at_all():
    # e.g. systemd-boot: no /boot/grub or /boot/grub2 directory at all.
    # Must not even get to the dual-boot signal check.
    with patch("os.path.isdir", return_value=False), patch.object(
        sh, "detect_drive_facts", return_value={"fs.ntfs_present"}
    ) as drive_facts:
        assert sh._detect_grub_os_prober_issue() == set()
    drive_facts.assert_not_called()


def test_own_efi_dirs_are_not_treated_as_another_os():
    with patch.object(sh, "os") as mocked_os:
        mocked_os.listdir.return_value = ["BOOT", "ubuntu"]
        assert sh._other_os_efi_entries() == set()


def test_foreign_efi_dir_is_reported():
    with patch.object(sh, "os") as mocked_os:
        mocked_os.listdir.return_value = ["BOOT", "ubuntu", "Microsoft"]
        assert sh._other_os_efi_entries() == {"Microsoft"}


def test_audio_conflict_detected_when_both_installed_and_not_masked():
    with patch.object(
        sh, "_dpkg_installed", side_effect=lambda pkg: pkg in {"pulseaudio", "pipewire-pulse"}
    ), patch.object(sh, "_user_service_masked", return_value=False):
        assert sh._detect_audio_conflict() == {"audio.pulseaudio_pipewire_conflict"}


def test_audio_conflict_absent_when_only_one_installed():
    with patch.object(sh, "_dpkg_installed", side_effect=lambda pkg: pkg == "pipewire-pulse"):
        assert sh._detect_audio_conflict() == set()


def test_audio_conflict_absent_when_pulseaudio_already_masked():
    # The user (or a previous migration) already disabled pulseaudio
    # deliberately; the package being present is just a leftover.
    with patch.object(
        sh, "_dpkg_installed", side_effect=lambda pkg: pkg in {"pulseaudio", "pipewire-pulse"}
    ), patch.object(sh, "_user_service_masked", return_value=True):
        assert sh._detect_audio_conflict() == set()


def test_ufw_inactive_detected():
    with patch("shutil.which", return_value="/usr/sbin/ufw"), patch.object(
        sh, "_service_active", return_value=False
    ), patch.object(sh, "_run", return_value="Status: inactive\n"):
        assert sh._detect_ufw_inactive() == {"firewall.ufw_inactive"}


def test_ufw_active_produces_no_fact():
    with patch("shutil.which", return_value="/usr/sbin/ufw"), patch.object(
        sh, "_service_active", return_value=False
    ), patch.object(sh, "_run", return_value="Status: active\n"):
        assert sh._detect_ufw_inactive() == set()


def test_ufw_not_flagged_when_firewalld_already_active():
    with patch("shutil.which", return_value="/usr/sbin/ufw"), patch.object(
        sh, "_service_active", return_value=True
    ), patch.object(sh, "_run") as run:
        assert sh._detect_ufw_inactive() == set()
    run.assert_not_called()  # shouldn't even bother checking ufw's own status
