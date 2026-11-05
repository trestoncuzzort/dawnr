"""Refusal regressions against the real Linux 6.18.60 olddefconfig output."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


HARDWARE = Path(__file__).resolve().parents[1] / "hardware"
SPEC = importlib.util.spec_from_file_location("hardware_kernel", HARDWARE / "kernel.py")
kernel = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kernel)


class HardwareKernelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tup-hardware-config-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / ".config"
        self.original = (HARDWARE / "linux-6.18.60-x86_64.config").read_text()
        self.path.write_text(self.original)

    def test_real_olddefconfig_keeps_wired_driver_and_firewall_floor(self):
        kernel.check(self.path)

    def test_lost_dependency_or_module_refuses(self):
        for symbol, value in (("NF_TABLES_INET", "y"), ("NFT_CT", "y"), ("NFT_LIMIT", "y"),
                              ("PACKET", "y"), ("R8169", "m"), ("VIRTIO_NET", "y"),
                              ("IRQ_REMAP", "y"), ("PVH", "y"), ("NVME_HWMON", "y"), ("KVM_AMD", "m"),
                              ("VFIO_PCI", "m"), ("VFIO_IOMMU_TYPE1", "m"), ("WIREGUARD", "m"),
                              ("NFT_REJECT_INET", "m"), ("DM_CRYPT", "m"), ("SP5100_TCO", "m"),
                              ("SENSORS_NCT6775", "m"), ("USB_RTL8152", "m"), ("DRM_AMDGPU", "m"),
                              ("CFS_BANDWIDTH", "y"), ("BLK_DEV_THROTTLING", "y"), ("SCHED_CORE", "y"),
                              ("IPV6_MULTIPLE_TABLES", "y"),
                              ("NF_TABLES_NETDEV", "y"), ("NF_TABLES_BRIDGE", "m"), ("VFIO_PCI_VGA", "y"),
                              ("TRANSPARENT_HUGEPAGE_MADVISE", "y")):
            self.assertIn(f"CONFIG_{symbol}={value}\n", self.original)
            self.path.write_text(self.original.replace(f"CONFIG_{symbol}={value}\n", f"# CONFIG_{symbol} is not set\n"))
            with self.subTest(symbol=symbol), self.assertRaises(kernel.Refusal):
                kernel.check(self.path)

    def test_late_microcode_cannot_silently_replace_early_loading_policy(self):
        self.path.write_text(self.original.replace("# CONFIG_MICROCODE_LATE_LOADING is not set", "CONFIG_MICROCODE_LATE_LOADING=y"))
        with self.assertRaisesRegex(kernel.Refusal, "MICROCODE_LATE_LOADING"):
            kernel.check(self.path)

    def test_probe_floor_tristates_stay_modules(self):
        for symbol in ("KVM", "VFIO", "FUSE_FS", "DRM_AMDGPU", "TAP"):
            self.assertIn(f"CONFIG_{symbol}=m\n", self.original)
            self.path.write_text(self.original.replace(f"CONFIG_{symbol}=m\n", f"CONFIG_{symbol}=y\n"))
            with self.subTest(symbol=symbol), self.assertRaisesRegex(kernel.Refusal, symbol):
                kernel.check(self.path)

    def test_forbidden_signature_driver_iommu_and_firmware_choices_refuse(self):
        unset = "# CONFIG_{} is not set\n"
        for symbol, old, new in (
                ("MODULE_SIG_FORCE", "CONFIG_MODULES=y\n", "CONFIG_MODULES=y\nCONFIG_MODULE_SIG_FORCE=y\n"),
                ("DRM_NOUVEAU", unset.format("DRM_NOUVEAU"), "CONFIG_DRM_NOUVEAU=m\n"),
                ("VFIO_NOIOMMU", unset.format("VFIO_NOIOMMU"), "CONFIG_VFIO_NOIOMMU=y\n"),
                ("TRANSPARENT_HUGEPAGE_ALWAYS", unset.format("TRANSPARENT_HUGEPAGE_ALWAYS"),
                 "CONFIG_TRANSPARENT_HUGEPAGE_ALWAYS=y\n"),
                ("EXTRA_FIRMWARE", 'CONFIG_EXTRA_FIRMWARE=""\n', 'CONFIG_EXTRA_FIRMWARE="amdgpu/gc_10_3_6_me.bin"\n')):
            self.assertIn(old, self.original)
            self.path.write_text(self.original.replace(old, new))
            with self.subTest(symbol=symbol), self.assertRaisesRegex(kernel.Refusal, symbol):
                kernel.check(self.path)

    def test_retained_fragment_config_and_record_describe_the_same_run(self):
        record = json.loads((HARDWARE / "KCONFIG-QUALIFICATION.json").read_bytes())
        sha256 = lambda raw: hashlib.sha256(raw).hexdigest()
        self.assertEqual((HARDWARE / "wired-host.config").read_bytes(), kernel.fragment().encode())
        self.assertEqual(record["inputs"]["hardware_fragment_sha256"], sha256(kernel.fragment().encode()))
        self.assertEqual(record["inputs"]["boot_fragment_sha256"],
                         sha256(sys.modules["tup.boot.kernel"].fragment().encode()))
        self.assertEqual(record["config_sha256"], sha256((HARDWARE / "linux-6.18.60-x86_64.config").read_bytes()))
        self.assertEqual([step["exit_code"] for step in record["steps"]], [0] * 5)
        self.assertEqual((record["jobs"], record["kernel_compiled"], record["target_booted"]), (1, False, False))

    def test_hardware_check_still_requires_existing_boot_floor(self):
        self.path.write_text(self.original.replace("CONFIG_EFI_STUB=y", "# CONFIG_EFI_STUB is not set"))
        with self.assertRaisesRegex(kernel.Refusal, "EFI_STUB"):
            kernel.check(self.path)


if __name__ == "__main__":
    unittest.main()
