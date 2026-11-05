#!/usr/bin/env python3
"""Extend the existing boot floor with the reviewed wired-host and probe requirements."""
import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tup.boot.inputs import Refusal, check_config
from tup.boot.kernel import LFS, SYSTEMD, DISABLED

# Linux 6.18.60 Kconfig and systemd v261 README; no external NIC driver.
BUILTIN = """NET UNIX PACKET INET IP_MULTICAST IPV6 NETDEVICES ETHERNET PCI
NET_VENDOR_REALTEK FW_LOADER VIRTIO_PCI VIRTIO_NET NETFILTER NETFILTER_ADVANCED
NETFILTER_NETLINK NF_CONNTRACK NF_TABLES NF_TABLES_INET NF_TABLES_IPV4
NF_TABLES_IPV6 NFT_CT NFT_LIMIT BPF BPF_SYSCALL BPF_JIT CGROUP_BPF NET_SCHED
NET_SCH_FQ_CODEL CPU_SUP_AMD MICROCODE""".split()
MODULES = ["R8169"]
OFF = ["MICROCODE_LATE_LOADING"]

# Probe/virtualization/recovery floor, read from the 6.18.60 Kconfig files that
# README.md links. Bool options are built in and every tristate is a module,
# except NF_NAT, HWMON and CPU_FREQ_GOV_PERFORMANCE: x86_64_defconfig already
# builds those in, and NVME_HWMON needs HWMON=y beside the built-in NVME_CORE.
BUILTIN += """VIRTUALIZATION HYPERVISOR_GUEST PARAVIRT KVM_GUEST PVH IOMMU_SUPPORT
AMD_IOMMU IRQ_REMAP VIRTIO_MMIO_CMDLINE_DEVICES NF_NAT HWMON NVME_HWMON WATCHDOG
RAS IKCONFIG_PROC CPU_FREQ X86_AMD_PSTATE CPU_FREQ_GOV_SCHEDUTIL
CPU_FREQ_GOV_PERFORMANCE NTFS3_LZX_XPRESS""".split()
MODULES += """KVM KVM_AMD VHOST_NET VHOST_VSOCK VSOCKETS TUN MACVLAN MACVTAP BRIDGE
VETH VFIO VFIO_PCI VIRTIO_BALLOON VIRTIO_MMIO FUSE_FS VIRTIO_FS HW_RANDOM_VIRTIO
VIRTIO_VSOCKETS WIREGUARD NFT_NAT NFT_MASQ NFT_REJECT NFT_FIB_IPV4 NFT_FIB_IPV6
NFT_FIB_INET NTFS3_FS UDF_FS DM_CRYPT DM_SNAPSHOT DM_THIN_PROVISIONING DM_VERITY
CRYPTO_XTS CRYPTO_AES_NI_INTEL ZRAM CRYPTO_USER_API_HASH CRYPTO_USER_API_SKCIPHER
BLK_DEV_NBD SENSORS_K10TEMP SENSORS_NCT6775 SENSORS_ASUS_EC SP5100_TCO EDAC
EDAC_DECODE_MCE EDAC_AMD64 I2C_PIIX4 I2C_CHARDEV SENSORS_SPD5118 IKCONFIG
CPU_FREQ_GOV_POWERSAVE USB_USBNET USB_RTL8152 USB_NET_AX88179_178A DRM_AMDGPU""".split()
# Promptless symbols that Kconfig derives from the requests: checked, never requested.
DERIVED = ["TAP", "NFT_REJECT_INET", "VFIO_IOMMU_TYPE1"]
OFF += ["MODULE_SIG_FORCE", "DRM_NOUVEAU", "VFIO_NOIOMMU"]
# USB_USBNET is needed only for the two wired fallback chip families above. Its
# default-y minidrivers would turn any CDC gadget that is plugged in (a phone,
# a hostile device) into a network link that the wired DHCP profile configures.
OFF += """USB_NET_CDCETHER USB_NET_CDC_NCM USB_NET_CDC_SUBSET USB_NET_NET1080
USB_NET_ZAURUS USB_NET_AX8817X""".split()
# x86_64_defconfig's default governor is userspace, which holds whatever
# frequency was last set if amd-pstate does not bind (CPPC off in firmware)
# and acpi-cpufreq takes over. A compute host must scale with load by default.
BUILTIN += ["CPU_FREQ_DEFAULT_GOV_SCHEDUTIL"]
OFF += ["CPU_FREQ_DEFAULT_GOV_USERSPACE"]
# Later stages in HEADLESS-GOAL.md need these, and most are bools that only a
# kernel rebuild could add: CPU quotas for guest and job cgroups (H39), core
# scheduling between mutually untrusted guests (H49), IPv6 policy routing for
# an overlay network (H26), the nftables netdev and bridge families for guest
# anti-spoofing (H46), the legacy VGA ranges of an assigned graphics card
# (H43), and huge pages on request (madvise) for guests and compute jobs.
BUILTIN += """CFS_BANDWIDTH SCHED_CORE IPV6_MULTIPLE_TABLES NF_TABLES_NETDEV VFIO_PCI_VGA
TRANSPARENT_HUGEPAGE TRANSPARENT_HUGEPAGE_MADVISE""".split()
MODULES += ["NF_TABLES_BRIDGE", "NFT_BRIDGE_META"]
OFF += ["TRANSPARENT_HUGEPAGE_ALWAYS"]


def fragment():
    return ("# Linux 6.18.60 desktop wired network/firewall and early microcode floor.\n"
            "# Merge after x86_64_defconfig and tup/boot/kernel.py fragment.\n"
            "# nft_counter, meta, lookup, payload and verdicts are nf_tables core objects.\n"
            "# Probe/virtualization/recovery floor: bool options built in, tristates as modules.\n"
            + "".join("CONFIG_" + symbol + "=y\n" for symbol in BUILTIN)
            + "".join("CONFIG_" + symbol + "=m\n" for symbol in MODULES)
            + "".join("# CONFIG_" + symbol + " is not set\n" for symbol in OFF))


def check(path):
    values = check_config(path)
    missing = [name for name in SYSTEMD + LFS + BUILTIN if values.get("CONFIG_" + name) != "y"]
    missing += [name for name in MODULES + DERIVED if values.get("CONFIG_" + name) != "m"]
    missing += [name for name in DISABLED + OFF if values.get("CONFIG_" + name) not in {None, "n"}]
    # Module firmware comes from the root filesystem; nothing is linked into the image.
    missing += ["EXTRA_FIRMWARE"] if values.get("CONFIG_EXTRA_FIRMWARE", '""') != '""' else []
    if missing:
        raise Refusal("hardware/boot requirements lost during Kconfig resolution: " + ", ".join(missing))
    return values


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fragment", "check"))
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == "fragment":
            print(fragment(), end="")
        else:
            if args.config is None:
                raise Refusal("check requires the actual post-olddefconfig .config")
            check(args.config)
            print("wired-host configuration accepted; kernel build and hardware behavior remain untested")
    except (OSError, ValueError) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
