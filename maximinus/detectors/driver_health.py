"""Verify GPU/CPU drivers are actually installed *and functioning*, and
flag known conflict patterns — not just "is a driver package present".

This is what catches the classic Mint/Ubuntu nvidia failure mode: two
driver packages (or the proprietary driver and nouveau) both present, so
apt/dkms/the kernel can't cleanly settle on one, and the GPU ends up with
no working driver at all despite something being "installed".

All of this is read-only detection. Remediation (purging a conflicting
package, blacklisting nouveau, enrolling a MOK key) touches things that
can break the display, so it's surfaced as guidance for the user to run
themselves, never executed automatically.
"""

import shutil
import subprocess

from .hardware import detect_hardware_facts


def _run(cmd):
    if shutil.which(cmd[0]) is None:
        return ""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def _dpkg_installed(patterns):
    """Installed package names (any of the given dpkg name globs)."""
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Package} ${Status}\n", *patterns],
        capture_output=True,
        text=True,
        check=False,
    )
    installed = set()
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and "install ok installed" in parts[1]:
            installed.add(parts[0])
    return installed


def _loaded_kernel_modules():
    try:
        with open("/proc/modules", encoding="utf-8") as fh:
            return {line.split()[0] for line in fh if line.strip()}
    except OSError:
        return set()


def _nvidia_smi_ok():
    if shutil.which("nvidia-smi") is None:
        return None  # unknown, not installed
    result = subprocess.run(
        ["nvidia-smi"], capture_output=True, text=True, timeout=10, check=False
    )
    return result.returncode == 0


def _secure_boot_enabled():
    out = _run(["mokutil", "--sb-state"]).lower()
    return "secureboot enabled" in out.replace(" ", "")


def _nvidia_health_facts():
    facts = set()
    nvidia_pkgs = _dpkg_installed(["nvidia-driver-*", "nvidia-[0-9]*"])
    modules = _loaded_kernel_modules()
    nvidia_loaded = "nvidia" in modules
    nouveau_loaded = "nouveau" in modules

    if len(nvidia_pkgs) > 1:
        facts.add("gpu.nvidia_conflicting_packages")

    if nvidia_pkgs and not nvidia_loaded:
        facts.add("gpu.nvidia_module_not_loaded")
        if nouveau_loaded:
            facts.add("gpu.nvidia_nouveau_conflict")
        if _secure_boot_enabled():
            facts.add("gpu.secureboot_may_block_nvidia")

    if nvidia_loaded:
        smi_ok = _nvidia_smi_ok()
        if smi_ok is False:
            facts.add("gpu.nvidia_smi_failing")

    return facts


def _amd_health_facts():
    facts = set()
    modules = _loaded_kernel_modules()
    amdgpu_loaded = "amdgpu" in modules
    radeon_loaded = "radeon" in modules

    if not amdgpu_loaded and not radeon_loaded:
        facts.add("gpu.amd_module_not_loaded")
    elif amdgpu_loaded and radeon_loaded:
        facts.add("gpu.amd_radeon_amdgpu_conflict")

    return facts


def _cpu_microcode_conflict_facts(hw_facts):
    facts = set()
    intel_pkg = _dpkg_installed(["intel-microcode"])
    amd_pkg = _dpkg_installed(["amd64-microcode"])

    if "cpu.microcode_amd" in hw_facts and intel_pkg:
        facts.add("cpu.microcode_wrong_vendor_installed")
    if "cpu.microcode_intel" in hw_facts and amd_pkg:
        facts.add("cpu.microcode_wrong_vendor_installed")

    return facts


def detect_driver_health_facts():
    hw_facts = detect_hardware_facts()
    facts = set()

    if "gpu.nvidia" in hw_facts:
        facts |= _nvidia_health_facts()
    if "gpu.amd" in hw_facts:
        facts |= _amd_health_facts()

    facts |= _cpu_microcode_conflict_facts(hw_facts)
    return facts
