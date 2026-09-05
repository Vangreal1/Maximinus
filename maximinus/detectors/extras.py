"""A handful of common fresh-install gaps beyond drivers and drive
integration: laptop power management, firmware updates, printing, media
codecs, and low memory with no swap configured.

Facts produced:
  power.tlp_missing        — this is a laptop (has a battery) with no
                              power-management tool installed or active
  power.tlp_ppd_conflict   — tlp is installed AND power-profiles-daemon
                              (Mint/GNOME's own default) is also active;
                              these two are known to fight over the same
                              hardware knobs
  firmware.fwupd_missing   — no tool to check for/apply firmware updates
  media.codecs_missing     — common extra codecs aren't installed
  printing.cups_missing    — no printing system installed at all
  mem.low_ram_no_swap      — low total RAM and no swap of any kind

Several of these checks specifically look for a *different* tool already
covering the same job before recommending one, since Mint (and other
distros) increasingly ship their own defaults out of the box. Recommending
a second tool on top of one already active is exactly the "two things
fighting over the same job" mistake this project exists to catch.
"""

import shutil
import subprocess

from .hardware import _run  # shared subprocess-with-fallback helper

LOW_RAM_THRESHOLD_KB = 4 * 1024 * 1024  # 4 GiB


def _dpkg_installed(pkg):
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", pkg],
        capture_output=True,
        text=True,
        check=False,
    )
    return "install ok installed" in result.stdout


def _service_active(unit):
    if shutil.which("systemctl") is None:
        return False
    result = subprocess.run(
        ["systemctl", "is-active", unit], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() == "active"


def _is_laptop():
    return bool(_run(["sh", "-c", "ls /sys/class/power_supply/ 2>/dev/null | grep -i ^BAT"]).strip())


def _total_ram_kb():
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def _has_any_swap():
    try:
        with open("/proc/swaps", encoding="utf-8") as fh:
            lines = fh.readlines()
        return len(lines) > 1  # first line is just the header
    except OSError:
        return True  # if we can't tell, don't recommend adding more swap


def detect_power_management_facts():
    if not _is_laptop():
        return set()

    tlp_installed = _dpkg_installed("tlp")
    ppd_active = _service_active("power-profiles-daemon")

    if tlp_installed and ppd_active:
        # A known real conflict: both manage the same CPU/power hardware
        # and fight over it. Mint ships power-profiles-daemon by default,
        # so this happens whenever tlp gets installed on top of it.
        return {"power.tlp_ppd_conflict"}

    if not tlp_installed and not ppd_active:
        return {"power.tlp_missing"}

    return set()  # exactly one of the two is handling it already, fine as-is


def detect_firmware_update_facts():
    if shutil.which("fwupdmgr") is None and not _dpkg_installed("fwupd"):
        return {"firmware.fwupd_missing"}
    return set()


def detect_codec_facts():
    if not _dpkg_installed("libavcodec-extra"):
        return {"media.codecs_missing"}
    return set()


def detect_printing_facts():
    if not _dpkg_installed("cups"):
        return {"printing.cups_missing"}
    return set()


def detect_swap_facts():
    total_kb = _total_ram_kb()
    if total_kb is not None and total_kb < LOW_RAM_THRESHOLD_KB and not _has_any_swap():
        return {"mem.low_ram_no_swap"}
    return set()


def detect_extras_facts():
    facts = set()
    facts |= detect_power_management_facts()
    facts |= detect_firmware_update_facts()
    facts |= detect_codec_facts()
    facts |= detect_printing_facts()
    facts |= detect_swap_facts()
    return facts
