# Offline boot host tools

The [2026-11-05 qualification record](host-qualification-20261105.json) records
a successful build of all three tools, a real zstd metadata roundtrip and an
inspected UEFI smoke ISO. It retains hashes for the successful run and the two
font-related failures. No TUP boot is claimed.

`host_tools.py` builds dracut 112, GRUB 2.14 for x86_64 EFI, and squashfs-tools
4.7.5 in a fresh private workspace. Its inputs are `host-sources.json`, the
retained `evidence/` directory and an offline archive cache. It reuses
`tup.sources.source_lock.verify_record`; the LFS core catalog and lock remain
separate. No downloads, TUP root access, mounts, device writes, firmware-variable
writes or target installations occur in this entrypoint.

The reviewed host catalog SHA256 is
`ac8e4892c4165cd20f943ec695e5cac07aefc306c231030f9b30274a8e764619`.
The selected source authentication is:

| Component | Authentication |
| --- | --- |
| dracut 112 | Detached upstream OpenPGP signature with the reviewed current maintainer primary; exact bytes also match the independently signed Gentoo snapshot. |
| GRUB 2.14 | Exact upstream archive authenticated by the Gentoo snapshot Manifest. This is distributor authentication, not a claim that GRUB's stale upstream key passed. |
| squashfs-tools 4.7.5 | Official GitHub release asset SHA256, independently corroborated by the Gentoo snapshot Manifest. |

The archive cache also needs the verification dependency
`gentoo-20261103.tar.xz`, SHA256
`923b3132d9214cee3f59fa2b56a3af27a0287c8587576c99ebcd5b24e537a194`.
The catalog records all source URLs, SHA256 pins, signature/key material and
snapshot members. The signed snapshot's exact archive size/SHA512 is checked,
not merely a downloaded standalone Manifest. Key policy and catalog bytes are
reviewed inputs; they are not self-authenticating. No provenance exception is
accepted for these host tools.

The build host needs Python >=3.12, Bash, GCC, make, binutils, bison, flex,
gettext, texinfo, help2man, pkg-config and the libkmod, zlib, liblzma, liblzo2,
liblz4 and libzstd development packages. It also needs authenticated distribution
packages providing GPG, cpio, gzip, xorriso and mtools. Provision the host with
its normal authenticated package manager before this script. It never runs one.
The tested host was Ubuntu 24.04 x86_64 with GCC 13.3.0 and libkmod 31.
Dracut's optional JSON support needs libsystemd >=257; it was disabled on this
host. The target-systemd live module remains installed. Rust cpio and generated
dracut documentation are explicitly disabled.

Run from an LF checkout inside the isolated Linux builder:

```sh
python3 tup/boot/host_tools.py \
  --catalog tup/boot/host-sources.json \
  --catalog-sha256 ac8e4892c4165cd20f943ec695e5cac07aefc306c231030f9b30274a8e764619 \
  --cache "$TUP_BOOT_SOURCE_CACHE" --evidence tup/boot/evidence \
  --workspace "$TUP_FRESH_HOST_WORKSPACE" --jobs 2
```

The workspace must be new, absolute, below an existing parent, and free of
symlinks, whitespace and shell metacharacters. Its exclusive creation prevents
concurrent invocations from sharing a partial build. A failed workspace is
retained with `FAILED.txt` and logs; there is no implicit replay or overwrite.
Root is required inside this isolated builder solely because the metadata
qualification tests preserve numeric owners and set-ID bits. Authenticated
upstream build scripts execute trusted code; the prefix boundary is not a
sandbox against a malicious compiler or source package.

Every `make install` first writes a staging directory. Any file outside the
declared prefix, escaping symlink or collision between components refuses
publication. Dracut's default `/usr/lib/systemd/system` destination is explicitly
overridden. GRUB uses the book's 64-bit EFI build only. No `grub-install` call
exists. Compilation uses the supplied job count and installation is serial;
no inherited compiler, linker or make flags enter the build.

Qualification checks the actual executable versions, then writes and extracts a
small zstd SquashFS image without mounting it. It checks file bytes, numeric
UID/GID, mode 4750, an xattr, mtime, hardlinks and relative symlinks. It runs
`grub-script-check` and `grub-mkrescue` on a serial-console smoke configuration,
then requires an actual UEFI El Torito entry reported by xorriso. The smoke ISO
contains no TUP root or kernel and is explicitly **unbooted**.

The first real qualification exposed a GRUB dependency that fixture tools had
not modeled: the default font `unicode.pf2` was absent. Empty `--fonts=`,
`--themes=` and `--locales=` disable optional installed assets, but GRUB still
unconditionally renders an EFI/Mac media label. `--label-font` now selects
`share/grub/themes/starfield/dejavu_12.pf2`, already present in the authenticated
GRUB archive. Its exact hash is part of `TOOLS.json`. No extra font download or
unreviewed binary is introduced.

A successful run writes `SOURCES.json`, the host distribution package inventory,
full build/qualification logs, the private prefix, `TOOLS.json` and a flushed
`HOST-BUILD.json`. The tool lock is directly usable by `assemble.py`; use its
reported SHA256 as the externally reviewed lock pin. The lock includes the full
prefix, dracut framework and EFI module trees. Host distribution dependencies
and runtime libraries still depend on that builder's APT trust and retained
package inventory; this is not a hermetic-build claim. A package inventory alone
is not cryptographic package authentication.

Host qualification does not test dracut against the future TUP sysroot, boot the
ISO, establish reproducibility, prove Ventoy support or approve release. Those
gates remain open even when `HOST-BUILD.json` is complete.

## Target source preparation

`target-sources.json` has SHA256
`db116615b263036b548613ec853642cd0c6f10d4264d9919dbfdf67a56f925a2`.
It is preparation for the later isolated target layer, not a target build receipt:

- libaio 0.3.113: the book's Pagure URL returned 404 after Pagure's sunset.
  Gentoo's mirror supplies identical historical book bytes, authenticated by the
  signed snapshot's size/SHA512 record.
- LVM2 2.03.42: the keyserver copy of its maintainer key produced `EXPKEYSIG`
  despite GPG returning zero. It was rejected. The refreshed key published in
  Sourceware's official LVM2 download directory verifies the archive without an
  expired-key status. The full approved primary is recorded in the catalog.

Both records passed the same live source verifier. No target compile, LVM
service enablement or device regression suite has run. Build libaio/dmsetup
only in the later layer based on the completed core; do not run LVM's destructive
device tests on the preparation host.

Primary references: [dracut 112 release](https://github.com/dracut-ng/dracut/releases/tag/112),
[dracut configure](https://raw.githubusercontent.com/dracut-ng/dracut/112/configure),
[dracut Makefile](https://raw.githubusercontent.com/dracut-ng/dracut/112/Makefile),
[LFS EFI GRUB](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/grub.html),
[GRUB rescue implementation](https://git.savannah.gnu.org/cgit/grub.git/tree/util/grub-mkrescue.c?h=grub-2.14),
[SquashFS installation](https://raw.githubusercontent.com/plougher/squashfs-tools/4.7.5/Documentation/4.7.5/INSTALL),
[SquashFS release metadata](https://api.github.com/repos/plougher/squashfs-tools/releases/tags/4.7.5),
[Gentoo signing-key policy](https://www.gentoo.org/downloads/signatures/),
[BLFS libaio](https://www.linuxfromscratch.org/blfs/view/stable-systemd/general/libaio.html),
[BLFS LVM2](https://www.linuxfromscratch.org/blfs/view/stable-systemd/postlfs/lvm2.html),
and [LVM2 source/key directory](https://sourceware.org/ftp/lvm2/).
