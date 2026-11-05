#!/usr/bin/env python3
"""Extend the existing boot floor with the reviewed wired-host requirements."""
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


def fragment():
    return ("# Linux 6.18.60 desktop wired network/firewall and early microcode floor.\n"
            "# Merge after x86_64_defconfig and tup/boot/kernel.py fragment.\n"
            "# nft_counter, meta, lookup, payload and verdicts are nf_tables core objects.\n"
            + "".join("CONFIG_" + symbol + "=y\n" for symbol in BUILTIN)
            + "".join("CONFIG_" + symbol + "=m\n" for symbol in MODULES)
            + "".join("# CONFIG_" + symbol + " is not set\n" for symbol in OFF))


def check(path):
    values = check_config(path)
    missing = [name for name in SYSTEMD + LFS + BUILTIN if values.get("CONFIG_" + name) != "y"]
    missing += [name for name in MODULES if values.get("CONFIG_" + name) != "m"]
    missing += [name for name in DISABLED + OFF if values.get("CONFIG_" + name) not in {None, "n"}]
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
