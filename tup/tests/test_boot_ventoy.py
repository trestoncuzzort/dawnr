"""Ventoy protocol fixtures; no physical or virtual block device is accessed."""
import struct
import unittest

from tup.boot.inputs import Refusal
from tup.boot import ventoy


def fixture(path="/images/tup test.iso", filesystem=0):
    raw = bytearray(512)
    raw[:16] = ventoy.SIGNATURE
    raw[17:33] = bytes(range(16))
    struct.pack_into("<QHH", raw, 33, 32 * 1024**3, 1, filesystem)
    encoded = path.encode()
    raw[45:45 + len(encoded)] = encoded
    struct.pack_into("<Q", raw, 429, 12345678)
    raw[481:485] = b"TUP!"
    raw[16] = (-sum(raw)) & 255
    return bytes(raw)


class VentoyTests(unittest.TestCase):
    def test_efi_attributes_are_not_mistaken_for_payload(self):
        raw = fixture("/images/测试.iso")
        self.assertEqual(ventoy.parse_handoff(b"\x07\0\0\0" + raw, efivarfs=True)["iso_path"], "/images/测试.iso")
        with self.assertRaises(Refusal):
            ventoy.parse_handoff(b"\x07\0\0\0" + raw)

    def test_tampered_signature_checksum_and_length_refuse(self):
        raw = fixture()
        for damaged in (raw[:-1], raw + b"x", b"x" + raw[1:], raw[:80] + b"X" + raw[81:]):
            with self.subTest(damaged=damaged[:16]):
                with self.assertRaises(Refusal):
                    ventoy.parse_handoff(damaged)

    def test_path_traversal_controls_and_ambiguity_refuse(self):
        for path in ("/../root.iso", "/images/../../root.iso", "/images//root.iso", "relative.iso",
                     "/images/./root.iso", "/images\\root.iso", "/image\nroot.iso", "/not-an-iso"):
            with self.subTest(path=path):
                with self.assertRaises(Refusal):
                    ventoy.parse_handoff(fixture(path))

    def test_unknown_filesystem_refuses(self):
        with self.assertRaises(Refusal):
            ventoy.parse_handoff(fixture(filesystem=65535))
        malformed = bytearray(fixture())
        malformed[45] = 255
        malformed[16] = 0
        malformed[16] = (-sum(malformed)) & 255
        with self.assertRaisesRegex(Refusal, "UTF-8"):
            ventoy.parse_handoff(malformed)

    def test_partition_selection_uses_parent_marker_and_actual_sysfs_node(self):
        handoff = ventoy.parse_handoff(fixture())
        sector = bytearray(512)
        sector[384:400] = bytes.fromhex(handoff["disk_guid"])
        sector[440:444] = bytes.fromhex(handoff["disk_signature"])
        target = {"parent_sector": bytes(sector), "partition": 1, "filesystem": "exfat", "node": "/dev/nvme2n1p1"}
        other = {**target, "parent_sector": bytes(512), "node": "/dev/sda1"}
        self.assertEqual(ventoy.select_partition(handoff, [other, target]), "/dev/nvme2n1p1")
        self.assertEqual(ventoy.select_partition(handoff, [target, other]), "/dev/nvme2n1p1")
        with self.assertRaisesRegex(Refusal, "ambiguous"):
            ventoy.select_partition(handoff, [target, {**target, "node": "/dev/sdb1"}])
        with self.assertRaisesRegex(Refusal, "absent"):
            ventoy.select_partition(handoff, [other])


if __name__ == "__main__":
    unittest.main()
