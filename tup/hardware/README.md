# Wired desktop hardware floor

This profile extends Linux **6.18.60** `x86_64_defconfig` and the existing
[`boot/kernel.py`](../boot/kernel.py) fragment. It covers the observed Realtek
PCI ID **10ec:8125**, a virtio network device for external VM tests, systemd
networking, the remote lane's current dual-stack nftables rules, and AMD family
**19h** early microcode inputs. Since 2026-11-05 it also carries a probe,
virtualization and recovery floor (below), so that the first kernel build already
contains what the first physical boot is meant to probe. It does not qualify a
running device or kernel.

The actual Linux configuration check passed with one build job: upstream
`x86_64_defconfig`, upstream `scripts/kconfig/merge_config.sh -m`, then
`olddefconfig` with unknown-symbol warnings treated as errors. Both the existing
boot checker and this hardware checker passed. The full resulting configuration
is retained as `linux-6.18.60-x86_64.config`; `KCONFIG-QUALIFICATION.json` binds its
hash, fragments, source archive, tools and command-log hashes, and
`wired-host.config` is the hardware fragment of that run. **Nothing was compiled
or booted:** only the Kconfig host utilities (`conf`, `fixdep`) were built. No
kernel, module, firmware load, QEMU or hardware boot ran, so every statement
below about a driver is a statement about configuration and source text, not
about behavior.

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
  was inferred from the current firewall rules; the probe floor below adds NAT,
  masquerade, reject and fib expressions as modules for later stages only. This
  does not claim that every unused feature inherited from x86_64_defconfig has
  been minimized.
- `MICROCODE=y`, `CPU_SUP_AMD=y` and the boot floor's initrd support permit early
  loading. Late microcode loading stays disabled. A family container alone does
  not establish that the CPU's precise model/stepping has an applicable update.

## Probe, virtualization and recovery floor

The first physical boot of this kernel is the only cheap chance to probe KVM,
IOMMU groups, sensors and the watchdog (hurdles H31 and H42 in
[`HEADLESS-GOAL.md`](../HEADLESS-GOAL.md)), and later stages need separate-kernel
guests, a private overlay network and rescue access to existing disks (H40-H47).
A later kernel rebuild costs a full image cycle, so these options are present
now. Every name and dependency was read in the 6.18.60 Kconfig files linked
here; **bool options are built in and every tristate is a module**, and the boot
floor stays built in exactly as before. Links are to
`git.kernel.org/.../stable/linux.git/tree/<path>?h=v6.18.60`.

| Purpose | Requested (`=m` unless marked) | Kconfig |
|---|---|---|
| KVM host | `VIRTUALIZATION=y`, `KVM`, `KVM_AMD`, `IOMMU_SUPPORT=y`, `AMD_IOMMU=y`, `IRQ_REMAP=y` | [x86/kvm](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/x86/kvm/Kconfig?h=v6.18.60), [iommu](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/iommu/Kconfig?h=v6.18.60), [iommu/amd](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/iommu/amd/Kconfig?h=v6.18.60) |
| Guest plumbing on the host | `VHOST_NET`, `VHOST_VSOCK`, `VSOCKETS`, `TUN`, `MACVLAN`, `MACVTAP`, `BRIDGE`, `VETH` | [vhost](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/vhost/Kconfig?h=v6.18.60), [vmw_vsock](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/net/vmw_vsock/Kconfig?h=v6.18.60), [drivers/net](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/net/Kconfig?h=v6.18.60), [bridge](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/net/bridge/Kconfig?h=v6.18.60) |
| Device assignment | `VFIO`, `VFIO_PCI`; `VFIO_NOIOMMU` must stay off | [vfio](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/vfio/Kconfig?h=v6.18.60), [vfio/pci](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/vfio/pci/Kconfig?h=v6.18.60) |
| Same kernel as a guest | `HYPERVISOR_GUEST=y`, `PARAVIRT=y`, `KVM_GUEST=y`, `PVH=y`, `VIRTIO_BALLOON`, `VIRTIO_MMIO`, `VIRTIO_MMIO_CMDLINE_DEVICES=y`, `FUSE_FS`, `VIRTIO_FS`, `HW_RANDOM_VIRTIO`, `VIRTIO_VSOCKETS` | [x86](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/x86/Kconfig?h=v6.18.60), [virtio](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/virtio/Kconfig?h=v6.18.60), [fuse](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/fs/fuse/Kconfig?h=v6.18.60), [hw_random](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/char/hw_random/Kconfig?h=v6.18.60) |
| Overlay and guest networking | `WIREGUARD`, `NF_NAT=y`, `NFT_NAT`, `NFT_MASQ`, `NFT_REJECT`, `NFT_FIB_IPV4`, `NFT_FIB_IPV6`, `NFT_FIB_INET` | [netfilter](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/net/netfilter/Kconfig?h=v6.18.60), [ipv4](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/net/ipv4/netfilter/Kconfig?h=v6.18.60), [ipv6](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/net/ipv6/netfilter/Kconfig?h=v6.18.60) |
| Rescue and guest storage | `NTFS3_FS`, `UDF_FS`, `DM_CRYPT`, `DM_SNAPSHOT`, `DM_THIN_PROVISIONING`, `DM_VERITY`, `CRYPTO_XTS`, `CRYPTO_AES_NI_INTEL`, `CRYPTO_USER_API_HASH`, `CRYPTO_USER_API_SKCIPHER`, `ZRAM`, `BLK_DEV_NBD` | [ntfs3](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/fs/ntfs3/Kconfig?h=v6.18.60), [udf](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/fs/udf/Kconfig?h=v6.18.60), [md](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/md/Kconfig?h=v6.18.60), [crypto](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/crypto/Kconfig?h=v6.18.60), [x86/crypto](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/x86/crypto/Kconfig?h=v6.18.60), [zram](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/block/zram/Kconfig?h=v6.18.60), [block](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/block/Kconfig?h=v6.18.60) |
| Monitoring and recovery | `HWMON=y`, `NVME_HWMON=y`, `SENSORS_K10TEMP`, `SENSORS_NCT6775`, `SENSORS_ASUS_EC`, `WATCHDOG=y`, `SP5100_TCO`, `RAS=y`, `EDAC`, `EDAC_DECODE_MCE`, `EDAC_AMD64`, `I2C_PIIX4`, `IKCONFIG`, `IKCONFIG_PROC=y` | [hwmon](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/hwmon/Kconfig?h=v6.18.60), [nvme](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/nvme/host/Kconfig?h=v6.18.60), [watchdog](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/watchdog/Kconfig?h=v6.18.60), [ras](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/ras/Kconfig?h=v6.18.60), [edac](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/edac/Kconfig?h=v6.18.60), [i2c](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/i2c/busses/Kconfig?h=v6.18.60), [init](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/init/Kconfig?h=v6.18.60) |
| CPU frequency | `CPU_FREQ=y`, `X86_AMD_PSTATE=y`, `CPU_FREQ_GOV_SCHEDUTIL=y`, `CPU_FREQ_GOV_PERFORMANCE=y`, `CPU_FREQ_GOV_POWERSAVE` | [cpufreq](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/cpufreq/Kconfig?h=v6.18.60), [x86](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/cpufreq/Kconfig.x86?h=v6.18.60) |
| USB Ethernet fallback | `USB_USBNET`, `USB_RTL8152`, `USB_NET_AX88179_178A` | [net/usb](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/net/usb/Kconfig?h=v6.18.60) |
| AMD integrated graphics | `DRM_AMDGPU`; `DRM_NOUVEAU` off, `EXTRA_FIRMWARE` empty | [amdgpu](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/gpu/drm/amd/amdgpu/Kconfig?h=v6.18.60), [display](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/gpu/drm/amd/display/Kconfig?h=v6.18.60), [firmware loader](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/base/firmware_loader/Kconfig?h=v6.18.60) |
| Signing policy | `MODULE_SIG_FORCE` off, `MICROCODE_LATE_LOADING` off | [module](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/kernel/module/Kconfig?h=v6.18.60) |

`kernel.py check` additionally requires three promptless symbols that Kconfig
derives and that cannot be requested: `TAP=m` (selected by `MACVTAP`),
`NFT_REJECT_INET=m` (`default NFT_REJECT`) and `VFIO_IOMMU_TYPE1=m` (the legacy
VFIO container; `IOMMUFD` stays off).

### What the Kconfig files changed in the request

- **`R8152` does not exist.** The driver's symbol is `USB_RTL8152`.
  `USB_NET_AX88179_178A` depends on `USB_USBNET`, which was added; with it Kconfig
  defaults in `USB_NET_CDCETHER`, `USB_NET_CDC_NCM`, `USB_NET_CDC_SUBSET`,
  `USB_NET_NET1080`, `USB_NET_ZAURUS`, `USB_NET_AX8817X` and `USB_RTL8153_ECM`
  as modules. `r8152` names seven `rtl_nic/rtl8153*`/`rtl8156*` firmware patch
  files; none is staged, and what the driver does without them is unprobed.
- **`TAP` and `NFT_REJECT_INET` have no prompt** and are derived, as above.
  `NFT_FIB_INET` depends on `NFT_FIB_IPV4` and `NFT_FIB_IPV6`, both added.
- **`NF_NAT`, `HWMON` and `CPU_FREQ_GOV_PERFORMANCE` are tristate but stay
  built in.** `x86_64_defconfig` already builds them in and nothing inherited is
  demoted. `HWMON` could not be a module anyway: `NVME_HWMON` depends on
  `(NVME_CORE=y && HWMON=y) || (NVME_CORE=m && HWMON)` and the boot floor builds
  NVMe in.
- **`EDAC` depends on `RAS`**, which `x86_64_defconfig` leaves off; `RAS=y` was
  added. The 6.18 name is still `EDAC_AMD64`; it depends on `EDAC_DECODE_MCE`,
  `AMD_NB` and `AMD_NODE`. Its implied `AMD_ATL` stays off because
  `MEMORY_FAILURE` is off.
- **`DM_CRYPT` selects only CBC and ESSIV.** `CRYPTO_XTS` was not set, so the
  usual `aes-xts-plain64` LUKS mapping could not have been opened;
  `CRYPTO_XTS` and `CRYPTO_AES_NI_INTEL` were added as modules.
- **`VIRTIO_MMIO` alone finds no device on a command-line-described x86 guest**;
  `VIRTIO_MMIO_CMDLINE_DEVICES` (a bool inside the module) was added.
- **`ZRAM` resolved with the LZO-RLE backend only** (`ZRAM_BACKEND_FORCE_LZO`);
  no other compressor was requested.
- **`DRM_AMDGPU=m` forces one tristate built in:** `DRM_AMD_DC` is a bool that
  selects `CEC_CORE`, which therefore resolves to `y`. It does not build firmware
  in: `EXTRA_FIRMWARE` stays `""`, and the checker now refuses anything else.
- **`KVM_AMD_SEV` is absent** because `CRYPTO_DEV_SP_PSP` is off, and
  `KVM_INTEL` was not requested for this AMD host.
- **Xen was measured and left out.** Adding only `XEN=y` to this fragment
  resolved 39 further `=y` symbols, among them `XEN_PV` with `PARAVIRT_XXL`,
  `XEN_DOM0`, `SWIOTLB_XEN`, `XEN_BACKEND` and built-in block, network, console
  and keyboard frontends, and removed `X86_REQUIRED_FEATURE_PGE` and
  `X86_REQUIRED_FEATURE_PSE` from the bare-metal kernel. Pinning `XEN_PV` off
  and `XEN_PVH=y` still resolved 26 built-in symbols including
  `ARCH_HAS_DMA_OPS` and the built-in frontends
  ([x86/xen Kconfig](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/arch/x86/xen/Kconfig?h=v6.18.60)).
  `PVH=y` alone provides the x86/HVM direct-boot entry; a Xen decision under H40
  needs its own configuration run.

### What the source says about this board, unprobed

- `nct6775-core.c` has the `nct6799` chip kind, and `nct6775-platform.c` lists
  `TUF GAMING X670E-PLUS` among the boards reached through the ASUS ACPI
  interface. `asus-ec-sensors.c` matches the same board name, hence
  `SENSORS_ASUS_EC`. `k10temp.c` and `amd64_edac.c` have family 19h model 60h
  entries. Which of these bind on the actual board is a first-boot observation.
- `X86_AMD_PSTATE_DEFAULT_MODE` resolved to 3 (active, EPP), which offers the
  `performance` and `powersave` policies itself; `schedutil` serves the passive
  and guided modes.
- [`apu-asic-info-table.csv`](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/Documentation/gpu/amdgpu/apu-asic-info-table.csv?h=v6.18.60)
  lists Ryzen 7000 (AM5, Raphael) as GC 10.3.6, DCN 3.1.5, VCN 3.1.2, SDMA 5.2.6
  and PSP 13.0.5. The matching `MODULE_FIRMWARE` names are
  `amdgpu/gc_10_3_6_{ce,pfp,me,mec,mec2,rlc}.bin`, `psp_13_0_5_{toc,ta}.bin`,
  `sdma_5_2_6.bin`, `dcn_3_1_5_dmcub.bin` and `vcn_3_1_2.bin`. The WHENCE file of
  the authenticated linux-firmware 20261019 lists them under `LICENSE.amdgpu`.
  **None is selected or staged here.** `amdgpu` removes the firmware framebuffer
  of its own PCI device during initialization, so loading it without these files
  can cost that device's console; stage the files or keep the module from
  loading until they are.

### Size of the change

Counted with `grep -c '=m$'` and `grep -c '=y$'` on the two retained
configurations: **12 to 110 module symbols** and 1695 to 1760 built-in symbols
(5653 to 5890 lines). No symbol of the earlier configuration was removed or
changed. Of the 65 new `=y` symbols only `CEC_CORE` is a tristate; the others are
bools: `IRQ_REMAP`, `PVH`, `RAS`, `NVME_HWMON`, `IKCONFIG_PROC`, options compiled
into the new modules, and core hooks that KVM, vhost and the balloon select
(`PREEMPT_NOTIFIERS`, `USER_RETURN_NOTIFIER`, `VIRT_XFER_TO_GUEST_WORK`,
`VHOST_TASK`, `MEMORY_BALLOON`, `PAGE_REPORTING`, `MITIGATION_VMSCAPE`). The
module and image sizes in bytes are unknown until the kernel is compiled.

## Reproducing the qualification

`qualify_kconfig.py` runs the procedure against an authenticated, extracted
kernel source and a new output directory, and writes the fragments, the three
logs, `build/.config` and `KCONFIG-QUALIFICATION.json` there. It only reads the
source tree. Before anything runs it finds `linux-<release>.tar.xz` in the 13.1
source lock, checks the supplied archive against that digest and compares the
tree with the archive member by member; afterwards it compares the names, sizes
and mtimes of the whole tree with those taken before. It refuses an existing
output directory and one inside the source tree. One run takes about a minute:

```sh
MAKEFLAGS=-j1 nice -n 19 python3 "$TUP/hardware/qualify_kconfig.py" \
  --source "$LINUX_SOURCE" --archive "$CACHE/linux-6.18.60.tar.xz" --output "$REVIEW"
cp "$REVIEW/build/.config" "$TUP/hardware/linux-6.18.60-x86_64.config"
cp "$REVIEW/hardware.config" "$TUP/hardware/wired-host.config"
cp "$REVIEW/KCONFIG-QUALIFICATION.json" "$TUP/hardware/"
```

Run with the fragments of the previous commit, the script reproduced the
previously retained configuration byte for byte (SHA256 `08938add...fc8a9`) with
identical input and tool hashes; log hashes differ because the logs contain the
output path. The steps it performs are these, and they do not install anything.
`merge_config.sh` creates temporary files in its working directory, so it is run
from the new output directory and not, as this file used to show, from the
source tree:

```sh
python3 "$TUP/boot/kernel.py" fragment > "$REVIEW/boot.config"
python3 "$TUP/hardware/kernel.py" fragment > "$REVIEW/hardware.config"
export ARCH=x86_64 MAKEFLAGS=-j1 LC_ALL=C
export KCONFIG_WARN_UNKNOWN_SYMBOLS=1 KCONFIG_WERROR=1
make -C "$LINUX_SOURCE" O="$REVIEW/build" x86_64_defconfig
(cd "$REVIEW" && bash "$LINUX_SOURCE/scripts/kconfig/merge_config.sh" -m \
  -O "$REVIEW/build" "$REVIEW/build/.config" \
  "$REVIEW/boot.config" "$REVIEW/hardware.config")
make -C "$LINUX_SOURCE" O="$REVIEW/build" olddefconfig
python3 "$TUP/boot/kernel.py" check --config "$REVIEW/build/.config"
python3 "$TUP/hardware/kernel.py" check --config "$REVIEW/build/.config"
```

The retained configuration was resolved with the builder's host compiler, whose
version Kconfig records in `CC_VERSION_TEXT`. A kernel build inside the TUP root
uses a different compiler, so `olddefconfig` there may resolve compiler-dependent
symbols differently; run both checkers on the configuration that is actually
built.

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

Observed on 2026-11-05 before the probe floor: all four tests passed on Linux
(0.015 seconds) and Windows (0.076 seconds), with no skips. They remove required
dependency/driver symbols, enable forbidden late loading, and remove the existing
EFI boot floor to prove those changes refuse.

With the probe floor there are 14 tests in two files. `test_hardware_kernel.py`
also removes thirteen of the new symbols one at a time, turns five module
symbols into built-ins, enables `MODULE_SIG_FORCE`, `DRM_NOUVEAU`, `VFIO_NOIOMMU`
and a non-empty `EXTRA_FIRMWARE`, and requires that `wired-host.config`, the
retained configuration and the hashes in `KCONFIG-QUALIFICATION.json` describe
the same run; a changed boot or hardware fragment therefore fails until the
qualification is run again. `test_hardware_qualify.py` exercises the script's
refusals on a small fixture archive: existing output directory, output inside
the source tree, a release absent from the lock, a wrong archive, and changed,
missing or extra source entries. It does not run `make`.

Primary references: [Linux 6.18 Kconfig](https://www.kernel.org/doc/html/v6.18/kbuild/kconfig.html),
[Realtek upstream Kconfig](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/net/ethernet/realtek/Kconfig?h=v6.18.60),
[nftables build objects](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/net/netfilter/Makefile?h=v6.18.60),
[systemd v261 requirements](https://raw.githubusercontent.com/systemd/systemd/v261/README),
[firmware releases](https://www.kernel.org/pub/linux/kernel/firmware/),
[BLFS firmware installation](https://www.linuxfromscratch.org/blfs/view/13.1-systemd/postlfs/firmware.html),
and [kernel microcode loading](https://docs.kernel.org/arch/x86/microcode.html).
