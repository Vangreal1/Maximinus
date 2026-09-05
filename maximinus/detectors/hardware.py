"""Hardware detection via lspci/lsusb.

Facts produced:
  gpu.nvidia, gpu.amd, gpu.intel
  wifi.broadcom, wifi.realtek, wifi.intel
  cpu.microcode_intel, cpu.microcode_amd
"""

import shutil
import subprocess


def _run(cmd):
    if shutil.which(cmd[0]) is None:
        return ""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def detect_hardware_facts():
    facts = set()
    lspci = _run(["lspci", "-nnk"]).lower()

    gpu_lines = [
        line for line in lspci.splitlines() if "vga" in line or "3d controller" in line
    ]
    gpu_block = "\n".join(gpu_lines)
    if "nvidia" in gpu_block:
        facts.add("gpu.nvidia")
    if "amd" in gpu_block or "advanced micro devices" in gpu_block or "ati" in gpu_block:
        facts.add("gpu.amd")
    if "intel" in gpu_block:
        facts.add("gpu.intel")

    net_lines = [
        line
        for line in lspci.splitlines()
        if "network controller" in line or "wireless" in line or "ethernet controller" in line
    ]
    net_block = "\n".join(net_lines)
    if "broadcom" in net_block:
        facts.add("wifi.broadcom")
    if "realtek" in net_block:
        facts.add("wifi.realtek")
    if "intel" in net_block:
        facts.add("wifi.intel")

    cpuinfo = _run(["cat", "/proc/cpuinfo"]).lower()
    if "genuineintel" in cpuinfo:
        facts.add("cpu.microcode_intel")
    if "authenticamd" in cpuinfo:
        facts.add("cpu.microcode_amd")

    return facts
