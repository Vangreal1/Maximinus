"""Common fresh-install Ubuntu/Mint problems beyond GPU/CPU drivers.

Facts produced:
  apt.broken_state                       — interrupted dpkg/apt run
  dkms.headers_missing                   — DKMS modules present, matching
                                            kernel headers are not, so they
                                            silently fail to (re)build
  time.ntp_disabled                      — clock isn't kept in sync, which
                                            can break apt/TLS with "future"
                                            or "past" certificate errors
  grub.os_prober_disabled_with_other_os  — a likely dual-boot OS (Windows,
                                            via an NTFS partition, or a
                                            second Linux install, via its
                                            own EFI/<name> directory) exists
                                            but GRUB won't list it
  audio.pulseaudio_pipewire_conflict     — both audio servers installed
  firewall.ufw_inactive                  — ufw present but not enabled
"""

import os
import platform
import shutil
import subprocess

from .drives import detect_drive_facts
from .hardware import _run  # shared subprocess-with-fallback helper

# This machine's own EFI System Partition boot-loader directories — anything
# else under /boot/efi/EFI belongs to another OS (Windows, or a second Linux
# install), since every OS's installer creates its own EFI/<name> folder.
_OWN_EFI_DIR_NAMES = {"boot", "ubuntu", "linuxmint", "mint"}


def _dpkg_installed(pkg):
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", pkg],
        capture_output=True,
        text=True,
        check=False,
    )
    return "install ok installed" in result.stdout


def _read_file(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _detect_apt_broken_state():
    if shutil.which("dpkg") is None:
        return set()
    out = _run(["dpkg", "--audit"])
    return {"apt.broken_state"} if out.strip() else set()


def _detect_dkms_headers_missing():
    if shutil.which("dkms") is None:
        return set()
    dkms_out = _run(["dkms", "status"])
    if not dkms_out.strip():
        return set()
    headers_pkg = f"linux-headers-{platform.release()}"
    return set() if _dpkg_installed(headers_pkg) else {"dkms.headers_missing"}


def _detect_time_sync_disabled():
    if shutil.which("timedatectl") is None:
        return set()
    out = _run(["timedatectl", "show", "-p", "NTP", "--value"]).strip().lower()
    return {"time.ntp_disabled"} if out == "no" else set()


def _other_os_efi_entries():
    """Names of EFI/<name> directories on the ESP that aren't this machine's
    own — a read-only signal for "another OS is installed", Windows or a
    second Linux distro, without mounting anything new."""
    efi_dir = "/boot/efi/EFI"
    try:
        entries = os.listdir(efi_dir)
    except OSError:
        return set()
    return {e for e in entries if e.lower() not in _OWN_EFI_DIR_NAMES}


def _detect_grub_os_prober_issue():
    drive_facts = detect_drive_facts()
    other_os_present = "fs.ntfs_present" in drive_facts or bool(_other_os_efi_entries())
    if not other_os_present:
        return set()  # only act on a real dual-boot signal, not a guess
    os_prober_missing = shutil.which("os-prober") is None
    grub_defaults = _read_file("/etc/default/grub")
    prober_explicitly_disabled = any(
        line.strip().replace(" ", "") == "GRUB_DISABLE_OS_PROBER=true"
        for line in grub_defaults.splitlines()
        if not line.strip().startswith("#")
    )
    if os_prober_missing or prober_explicitly_disabled:
        return {"grub.os_prober_disabled_with_other_os"}
    return set()


def _detect_audio_conflict():
    if _dpkg_installed("pulseaudio") and _dpkg_installed("pipewire-pulse"):
        return {"audio.pulseaudio_pipewire_conflict"}
    return set()


def _detect_ufw_inactive():
    if shutil.which("ufw") is None:
        return set()
    out = _run(["ufw", "status"]).lower()
    return {"firewall.ufw_inactive"} if "inactive" in out else set()


def detect_system_health_facts():
    facts = set()
    facts |= _detect_apt_broken_state()
    facts |= _detect_dkms_headers_missing()
    facts |= _detect_time_sync_disabled()
    facts |= _detect_grub_os_prober_issue()
    facts |= _detect_audio_conflict()
    facts |= _detect_ufw_inactive()
    return facts
