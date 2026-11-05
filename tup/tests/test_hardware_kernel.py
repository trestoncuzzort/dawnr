"""Refusal regressions against the real Linux 6.18.60 olddefconfig output."""
import importlib.util
from pathlib import Path
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
                              ("PACKET", "y"), ("R8169", "m"), ("VIRTIO_NET", "y")):
            self.path.write_text(self.original.replace(f"CONFIG_{symbol}={value}\n", f"# CONFIG_{symbol} is not set\n"))
            with self.subTest(symbol=symbol), self.assertRaises(kernel.Refusal):
                kernel.check(self.path)

    def test_late_microcode_cannot_silently_replace_early_loading_policy(self):
        self.path.write_text(self.original.replace("# CONFIG_MICROCODE_LATE_LOADING is not set", "CONFIG_MICROCODE_LATE_LOADING=y"))
        with self.assertRaisesRegex(kernel.Refusal, "MICROCODE_LATE_LOADING"):
            kernel.check(self.path)

    def test_hardware_check_still_requires_existing_boot_floor(self):
        self.path.write_text(self.original.replace("CONFIG_EFI_STUB=y", "# CONFIG_EFI_STUB is not set"))
        with self.assertRaisesRegex(kernel.Refusal, "EFI_STUB"):
            kernel.check(self.path)


if __name__ == "__main__":
    unittest.main()
