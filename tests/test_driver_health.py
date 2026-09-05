from unittest.mock import patch

from maximinus.detectors import driver_health as dh


def _hw(*facts):
    return set(facts)


def test_conflicting_nvidia_packages_detected():
    with patch.object(
        dh, "_dpkg_installed", return_value={"nvidia-driver-535", "nvidia-driver-470"}
    ), patch.object(dh, "_loaded_kernel_modules", return_value={"nvidia"}), patch.object(
        dh, "_nvidia_smi_ok", return_value=True
    ):
        facts = dh._nvidia_health_facts()

    assert "gpu.nvidia_conflicting_packages" in facts


def test_nouveau_conflict_detected_when_driver_installed_but_nouveau_loaded():
    with patch.object(
        dh, "_dpkg_installed", return_value={"nvidia-driver-535"}
    ), patch.object(
        dh, "_loaded_kernel_modules", return_value={"nouveau"}
    ), patch.object(
        dh, "_secure_boot_enabled", return_value=False
    ):
        facts = dh._nvidia_health_facts()

    assert "gpu.nvidia_module_not_loaded" in facts
    assert "gpu.nvidia_nouveau_conflict" in facts


def test_secureboot_flagged_when_module_missing_and_secureboot_on():
    with patch.object(
        dh, "_dpkg_installed", return_value={"nvidia-driver-535"}
    ), patch.object(dh, "_loaded_kernel_modules", return_value=set()), patch.object(
        dh, "_secure_boot_enabled", return_value=True
    ):
        facts = dh._nvidia_health_facts()

    assert "gpu.secureboot_may_block_nvidia" in facts


def test_nvidia_smi_failure_flagged_when_module_loaded_but_smi_broken():
    with patch.object(dh, "_dpkg_installed", return_value={"nvidia-driver-535"}), patch.object(
        dh, "_loaded_kernel_modules", return_value={"nvidia"}
    ), patch.object(dh, "_nvidia_smi_ok", return_value=False):
        facts = dh._nvidia_health_facts()

    assert "gpu.nvidia_smi_failing" in facts


def test_healthy_nvidia_setup_produces_no_facts():
    with patch.object(dh, "_dpkg_installed", return_value={"nvidia-driver-535"}), patch.object(
        dh, "_loaded_kernel_modules", return_value={"nvidia"}
    ), patch.object(dh, "_nvidia_smi_ok", return_value=True):
        facts = dh._nvidia_health_facts()

    assert facts == set()


def test_amd_radeon_amdgpu_conflict_detected():
    with patch.object(dh, "_loaded_kernel_modules", return_value={"radeon", "amdgpu"}):
        facts = dh._amd_health_facts()

    assert "gpu.amd_radeon_amdgpu_conflict" in facts


def test_amd_no_module_loaded_detected():
    with patch.object(dh, "_loaded_kernel_modules", return_value=set()):
        facts = dh._amd_health_facts()

    assert "gpu.amd_module_not_loaded" in facts


def test_cpu_wrong_vendor_microcode_detected_on_amd_cpu():
    with patch.object(dh, "_dpkg_installed", side_effect=[{"intel-microcode"}, set()]):
        facts = dh._cpu_microcode_conflict_facts(_hw("cpu.microcode_amd"))

    assert "cpu.microcode_wrong_vendor_installed" in facts


def test_cpu_matching_microcode_produces_no_conflict():
    with patch.object(dh, "_dpkg_installed", side_effect=[set(), {"amd64-microcode"}]):
        facts = dh._cpu_microcode_conflict_facts(_hw("cpu.microcode_amd"))

    assert facts == set()
