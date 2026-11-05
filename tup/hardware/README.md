# Wired desktop hardware floor

This profile extends Linux **6.18.60** `x86_64_defconfig` and the existing
[`boot/kernel.py`](../boot/kernel.py) fragment. It covers the observed Realtek
PCI ID **10ec:8125**, a virtio network device for external VM tests, systemd
networking, the remote lane's current dual-stack nftables rules, and AMD family
**19h** early microcode inputs. It does not qualify a running device or kernel.

The actual Linux configuration check passed with one build job: upstream
`x86_64_defconfig`, upstream `scripts/kconfig/merge_config.sh -m`, then
`olddefconfig` with unknown-symbol warnings treated as errors. Both the existing
boot checker and this hardware checker passed. The full resulting configuration
is retained as `linux-6.18.60-x86_64.config`; `KCONFIG-QUALIFICATION.json` binds its
hash, fragments, source archive, tools and command-log hashes. Only Kconfig host
utilities were compiled; no kernel, module, firmware load or boot ran.

## Reused components and selected configuration

`kernel.py` is a small extension of the existing boot config checker. The
upstream Kconfig machinery resolves dependencies. There is no new config parser,
driver implementation or kernel build framework.

- `R8169=m` uses the upstream driver for 10ec:8125. Udev can load it with firmware
  available from the root filesystem; module installation and actual probe remain
  required. The exact hardware XID chooses among the five firmware alternatives.
- `VIRTIO_NET=y` remains built in from the boot floor for VM networking tests.
- `NF_TABLES`, `NF_TABLES_INET`, `NF_CONNTRACK`, `NFT_CT` and `NFT_LIMIT` are built
  in, with IPv4/IPv6 and packet sockets. Counters, payload/compare/lookup/meta,
  sets and verdicts are core `nf_tables` objects in 6.18.60; **NFT_COUNTER is not
  a selectable symbol**. No NAT, reject, flowtable or conntrack-helper requirement
  was inferred from the current firewall rules. This does not claim that every
  unused feature inherited from x86_64_defconfig has been minimized.
- `MICROCODE=y`, `CPU_SUP_AMD=y` and the boot floor's initrd support permit early
  loading. Late microcode loading stays disabled. A family container alone does
  not establish that the CPU's precise model/stepping has an applicable update.

Run this only against a disposable, already authenticated kernel source tree
and a new out-of-tree output directory. These commands do not install anything:

```sh
python3 "$TUP/boot/kernel.py" fragment > "$REVIEW/boot.config"
python3 "$TUP/hardware/kernel.py" fragment > "$REVIEW/hardware.config"
export ARCH=x86_64 MAKEFLAGS=-j1 LC_ALL=C
export KCONFIG_WARN_UNKNOWN_SYMBOLS=1 KCONFIG_WERROR=1
make -C "$LINUX_SOURCE" O="$REVIEW/build" x86_64_defconfig
(cd "$LINUX_SOURCE" && bash scripts/kconfig/merge_config.sh -m \
  -O "$REVIEW/build" "$REVIEW/build/.config" \
  "$REVIEW/boot.config" "$REVIEW/hardware.config")
make -C "$LINUX_SOURCE" O="$REVIEW/build" olddefconfig
python3 "$TUP/boot/kernel.py" check --config "$REVIEW/build/.config"
python3 "$TUP/hardware/kernel.py" check --config "$REVIEW/build/.config"
```

## Authenticated firmware and isolated staging

`firmware-source.json` selects upstream `linux-firmware-20261019.tar.xz`, SHA256
`a10d1ab5baf2c74ba92e8c7cf313e691696c26bddfa6df00db795e48d70cd4ca`.
The existing [`source_lock.verify_record`](../sources/source_lock.py) verified
the Gentoo 20261103 snapshot's OpenPGP signature, its exact package Manifest,
and the archive filename/size/SHA512. `FIRMWARE-VERIFICATION.json` retains that
result. This is distributor authentication of exact upstream archive bytes;
it is not a claim of a verified firmware-publisher signature.

The public evidence contains the approved Gentoo key, signature, official
key-policy material and exact Manifest. The large signed snapshot and firmware
archive stay in the external cache. To recheck using the existing verifier,
from the repository root:

```python
import json
from pathlib import Path
from tup.sources.source_lock import verify_record
record = json.loads(Path("tup/hardware/firmware-source.json").read_bytes())
result = verify_record(record, Path("/path/to/cache"),
                       Path("tup/hardware/evidence"), Path("/usr/bin/gpg"))
assert result["status"] == "verified"
```

Review/pin the record and evidence before invoking this code. The cache must
contain both `linux-firmware-20261019.tar.xz` and `gentoo-20261103.tar.xz`; this
does not alter the core's 94-source lock or frozen inputs.

`FIRMWARE-SELECTION.json` lists five regular `rtl_nic/rtl8125*.fw` files requested
by the 6.18.60 RTL8125 XID table, `amd-ucode/microcode_amd_fam19h.bin`, and their
two required license notices. The names are explicit; a wildcard does not choose
the device variant. `firmware-files.sha256` checks the selected extracted files.
`FIRMWARE-STAGING.json` records the actual isolated staging result: **8 regular
files, 164125 bytes**, all mode 0644, with identical source/destination hashes.
No firmware was installed on the host or running target.

The selected upstream release's `copy-firmware.sh` installs the entire WHENCE
inventory. Its current development branch has a path selector, but that option
does not exist in 20261019. This profile therefore follows BLFS's explicit
selected-file copy pattern, using GNU `install -D -m 0644`, rather than silently
depending on a newer script or rewriting the upstream installer:

```sh
cd "$AUTHENTICATED_FIRMWARE_SOURCE"
sha256sum --check "$TUP/hardware/firmware-files.sha256"
# STAGE must be a new disposable staging directory, never / or a live root.
mkdir "$STAGE"
for name in rtl8125a-3.fw rtl8125b-2.fw rtl8125d-1.fw rtl8125d-2.fw rtl8125bp-2.fw; do
  install -D -m 0644 "rtl_nic/$name" "$STAGE/usr/lib/firmware/rtl_nic/$name"
done
install -D -m 0644 amd-ucode/microcode_amd_fam19h.bin \
  "$STAGE/usr/lib/firmware/amd-ucode/microcode_amd_fam19h.bin"
for name in LICENSE.r8169 LICENSE.amd-ucode; do
  install -D -m 0644 "LICENSES/$name" "$STAGE/usr/share/licenses/linux-firmware/$name"
done
```

Keep both notices with redistributed firmware. Realtek permits redistribution
with its copyright notice; AMD's supplied license requires its full notice and
terms to accompany the binary. The staged files remain separate from the kernel.

## Remaining runtime gates

The current boot assembler explicitly passes `--no-early-microcode`. A later
boot-layer change must enable early loading after staging the authenticated AMD
input, inspect `kernel/x86/microcode/AuthenticAMD.bin` in the generated initrd,
and verify the actual CPU model/stepping and boot-time revision result. This
profile does not modify boot packaging or load microcode on the builder.

Next build the kernel/modules against the completed TUP core, install the matching
module/firmware inputs into a separate export, and test virtio networking plus
the exact firewall rules on that target. The real desktop must then establish
the NIC XID, selected firmware, link/renewal/recovery behavior, sustained traffic,
and remote access. Windows reporting a 1 Gbps link is not Linux qualification.
The USB RTL8852CU support gap remains open; these Ethernet and Bluetooth-looking
firmware names do not supply its driver. The actual 6.18.60 rtw89 Kconfig has
8851BU/8852BU USB support and 8852CE PCI support, but no 8852CU option or
rtw8852cu build entry. GPU, full hardware
stress, physical boot and release readiness remain unclaimed.

Focused refusal tests use the retained real olddefconfig output:

```sh
python3 -m unittest discover -s tup/tests -p 'test_hardware*.py' -v
```

Observed on 2026-11-05: all four tests passed on Linux (0.015 seconds) and
Windows (0.076 seconds), with no skips. They remove required dependency/driver
symbols, enable forbidden late loading, and remove the existing EFI boot floor
to prove those changes refuse.

Primary references: [Linux 6.18 Kconfig](https://www.kernel.org/doc/html/v6.18/kbuild/kconfig.html),
[Realtek upstream Kconfig](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/net/ethernet/realtek/Kconfig?h=v6.18.60),
[nftables build objects](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/net/netfilter/Makefile?h=v6.18.60),
[systemd v261 requirements](https://raw.githubusercontent.com/systemd/systemd/v261/README),
[firmware releases](https://www.kernel.org/pub/linux/kernel/firmware/),
[BLFS firmware installation](https://www.linuxfromscratch.org/blfs/view/13.1-systemd/postlfs/firmware.html),
and [kernel microcode loading](https://docs.kernel.org/arch/x86/microcode.html).
