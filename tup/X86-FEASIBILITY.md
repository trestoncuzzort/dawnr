# X86-FEASIBILITY — the x86_64 build on ubuntu-box

Probe run 2026-08-31 on ubuntu-box (Ubuntu 24.04, x86_64, 120 threads,
502 G RAM, no sudo). Scope: WS-8's one remaining real item — "same driver,
x86 book". This is a feasibility report, not a build; everything below is
either a measurement made today or is labeled UNMEASURED.

**Verdict: GO.** TCG guest works today; KVM guest is one admin line away and
is the recommended path; rootless chroot is measured dead on this box.

## Measured facts

1. **QEMU now has the x86_64 target.** `~/.local/opt/qemu-10.1.3` had
   aarch64-softmmu only (confirmed: `bin/` contained `qemu-system-aarch64`
   and no x86 binary). Rebuilt today from `qemu-10.1.3.tar.xz`, sha256
   `fbaa7a0d7a9a1deb5695b125916746ec28fe0de6275d4454f3e3bbaf8b339b53`
   (matches the pin), using the exact RUN-ON-UBUNTU.md no-sudo recipe — the
   micromamba `qemubuild` env survived the Aug 31 wipe. Target list:
   `aarch64-softmmu,x86_64-softmmu,x86_64-linux-user`. The third target is a
   deviation from the requested pair, added solely to produce `qemu-x86_64`
   for the TCG benchmark below. Installed to the same prefix; both system
   emulators report 10.1.3; `edk2-x86_64-code.fd`, `edk2-aarch64-code.fd`,
   and the SeaBIOS blobs are all present in `share/qemu`; a 5 s
   `-M q35 -accel tcg` smoke run stayed alive until killed.

2. **/dev/kvm is NOT usable by this user.** Device exists, `root:kvm` 0660,
   ACL grants rw only to user `gdm`; this account's groups are
   `user users`. `open(O_RDWR)` → EACCES;
   `qemu-system-x86_64 -accel kvm` → "Could not access KVM kernel module:
   Permission denied". KVM support is compiled in (`-accel help` lists kvm
   and tcg). ROADMAP WS-8 says tup "runs as a KVM guest on the Dell" — as of
   today that is aspiration, not fact, until an admin grants the kvm group.

3. **TCG overhead ≈ 14x per thread** (crude proxy, labeled as such):
   `cc1 -O2` on a generated 2000-function C file, byte-identical 634198-byte
   assembly out of both runs, rc=0 both: native 1.18–1.20 s; under
   `qemu-x86_64` user-mode TCG 16.51–16.74 s. Method note recorded so nobody
   repeats the mistake: benchmarking through the `gcc` driver measured
   nothing (1.27 s vs 1.32 s) because user-mode qemu hands `execve` children
   to the kernel and cc1 ran native. System-mode MTTCG parallelizes across
   vcpus, so the 14x applies per thread of compile work; fork/exec-heavy
   configure phases are typically worse than 14x.

4. **Rootless chroot is dead here.**
   `kernel.apparmor_restrict_unprivileged_userns = 1` (Ubuntu 24.04
   default). Measured, not assumed: `unshare -r` fails writing uid_map
   (EPERM); a raw `unshare(CLONE_NEWUSER)` from python succeeds but the
   process comes out capability-stripped — setgroups EACCES, uid_map EPERM,
   gid_map EPERM, `chroot()` EPERM, `unshare(CLONE_NEWNS)` EPERM. The
   setuid helpers `/usr/bin/newuidmap`/`newgidmap` are not installed even
   though `/etc/subuid` carries `user:362144:65536`. Probe caveat: a
   first attempt printed "OK" for the map writes because python's buffered
   close swallowed the flush error; re-measured with raw `os.write`.

5. **The x86 book exists in the shape the extractor expects.** Official LFS
   12.4 (SysV): `index.html` 200, `wget-list-sysv` 200,
   `chapter10/kernel.html` 200, and the TOC carries `href="chapterNN/…"`
   links matching the extractor's regex form.

6. **Wall-time anchor:** the arm64 build receipt
   (`receipts/BUILD-20260831T123738Z.md`) records **2.40 h machine time**
   for 139 pages with glibc/gcc/binutils suites, under near-native accel.

## What is arm64-specific, file by file

Reusable verbatim (measured: zero arch references): `driver.sh`,
`chain7.sh`, `chain8.sh`, `chain-home.sh`, `bundle_receipts.py`, and the
overrides `02-pkgmgt`, `04-symlinks`, `05-network`, `06-createfiles`,
`07-locale`, `29-shadow`, `37-bash`, `03-reboot`, `lib-judge.sh`. The
`/dev/vdb` assumption (LFS disk = build VM's second virtio disk, ESP =
vdb1 during build) lives in the VM provisioning, not in these scripts; an
x86_64 build VM must present the same second-disk layout.

Needs an x86_64 variant or edit:

| File | What changes |
|---|---|
| `extract_book.py` | One line: `BASE` from `…/~xry111/lfs/view/arm64/` to `https://www.linuxfromscratch.org/lfs/view/12.4/`. `book/` then regenerates itself; the built-in page-count-vs-index gate re-verifies the new TOC. Package versions differ between books (arm64 r12.4-42 tracks newer kernels); the wget-list resolution already handles that. |
| `overrides/03-kernel.sh` | Most arch-bound file. Its 23 config symbols were parsed from the arm64 book's kernel-page prose; `EFI_ZBOOT` and the `arch/arm64/boot/vmlinuz.efi` copy are arm64-only. Re-parse the x86 12.4 kernel page's prose; copy `arch/x86/boot/bzImage`; keep the four forced-in virtio `=y` additions. |
| `overrides/04-grub.sh` | Console `ttyAMA0` → `ttyS0,115200`; kernel filename changes with the book's version; and a real decision: the x86 book installs BIOS GRUB (i386-pc, no ESP), the arm64 leg was necessarily EFI. BIOS follows the book's own bytes and shrinks this override; EFI (`edk2-x86_64-code.fd` + `--removable`, now installed) keeps witness parity with arm64. Decide before extraction, it shapes fstab and the disk layout. |
| `overrides/02-fstab.sh` | `vda2`/virtio naming stays; the `/boot/efi` vfat line is dropped if the BIOS route is taken. |
| `overrides/06-usage.sh` | agetty on `ttyAMA0` → `ttyS0`. |
| `overrides/01-theend.sh` | Release strings: `arm64-r12.4` → `x86_64-12.4`; image name `tup-0.1-x86_64`. |
| `boot_witness.sh` | `qemu-system-aarch64 -M virt -accel hvf` + `/opt/homebrew` EDK2 paths (macOS-shaped) → `qemu-system-x86_64 -M q35 -accel kvm` (tcg fallback), firmware from `~/.local/opt/qemu-10.1.3/share/qemu/` or none for SeaBIOS. |
| `release.sh` | Same substitutions: name, firmware, accel. |
| `RUN-ON-UBUNTU.md`, `RUN-ON-WINDOWS.md` | x86_64 boot commands alongside the arm64 ones. |

## The three paths, honestly costed

- **KVM guest — recommended.** Blocked today only by /dev/kvm permissions;
  everything else is in place (emulator, firmware, driver, chain scripts).
  Near-native CPU. Anchored to the 2.40 h arm64 receipt and 120 host
  threads: **~2–4 h wall** for the build legs, plus VM provisioning.
  UNMEASURED: no x86_64 guest has actually booted here, KVM speed itself
  unmeasurable until access is granted.
- **TCG guest — available today, slow.** The 40 s boot-to-login of the
  arm64 image under pure TCG on this box is already witnessed
  (RUN-ON-UBUNTU.md), so the path is real. At ~14x per thread on compile
  work, partially recovered by MTTCG across many vcpus and lost again in
  serial configure phases: **~1–2 days wall, wide error bars.** UNMEASURED
  end to end; the 14x is a single-process compiler proxy, not a build.
- **Rootless chroot — NO-GO as this box is configured.** Would be native
  speed and VM-free, but the apparmor userns restriction strips every
  capability the LFS chroot legs need (chroot, mount, chown-to-many-uids).
  Unblocking needs an admin: `apparmor_restrict_unprivileged_userns=0` (or
  a profile) plus the `uidmap` package. Not worth asking for when the KVM
  ask is smaller.

## Unmeasured, would need witnessing

- Boot of any x86_64 guest OS on this box (no build-VM image downloaded;
  probe scope excluded multi-hour work).
- KVM acceleration (permission-blocked).
- Full x86_64 build wall time under either accelerator.
- The BIOS-vs-EFI decision for the x86 leg — a ruling to record, not a
  measurement to take.
- The regenerated x86 `book/` page set — the extractor's own count-vs-index
  gate is the witness for that, at extraction time.

## Exact next commands

1. Ask Ryan or Dr. Rahman to run (no sudo on this account):

       sudo gpasswd -a user kvm

2. After next login, verify — this line's output is the witness:

       bash -lc 'python3 -c "import os,fcntl;fd=os.open(\"/dev/kvm\",os.O_RDWR);print(\"KVM API\",fcntl.ioctl(fd,0xAE00))"'

3. First build-path step (runs today under TCG; add `-accel kvm` once step
   2 passes) — fetch scaffolding, hash before use, boot it:

       cd ~/tup && curl -LO https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img \
         && sha256sum noble-server-cloudimg-amd64.img   # record the hash in the receipt before first use
       ~/.local/opt/qemu-10.1.3/bin/qemu-system-x86_64 -M q35 -m 16G -smp 32 \
         -accel tcg -nographic -drive file=noble-server-cloudimg-amd64.img,format=qcow2,if=virtio

   (Provisioning the second virtio disk as `/mnt/lfs` and pointing
   `extract_book.py` at the 12.4 book follow; the BIOS/EFI ruling comes
   first.)

## Rulings and what was built (2026-09-02)

**BIOS, not EFI.** The x86 leg installs GRUB the way the x86 12.4 book does:
`i386-pc` to the MBR of a DOS-labelled disk with one ext4 partition, root on
`/dev/vda1`, no ESP, no swap. Reasons, in order: it is the book's own bytes
(the EFI route needs a second GRUB build from BLFS, which is a deviation
with no witness value); the boot witness keeps its shape (firmware plus the
disk and nothing else; SeaBIOS is bundled in the QEMU build, so there is no
firmware file to name); and the fstab and grub overrides shrink instead of
growing. The cost is stated: the arm64 and x86_64 images differ in partition
layout (`vda2` under an ESP versus `vda1` alone), and that difference is
recorded in each arch's `overrides/<arch>/ch10/fstab.sh`.

**KVM still denied.** `/dev/kvm` remains `root:kvm` with an ACL for `gdm`
only; the account's groups are unchanged. The leg therefore ran under TCG,
64 vcpus, 96 G, exactly as the "available today, slow" path above costed
it. Wall-clock numbers are in `receipts/BUILD-*.md` for this leg and are
the first end-to-end TCG measurement; the 14x-per-thread proxy above was a
single compiler.

**What changed in the tree to make one driver build two books:**

- `extract_book.py --arch x86_64` writes `book-x86_64/` with a
  `BOOK-SOURCE` marker; the arm64 default and `book/` are untouched.
- Overrides are matched by page name within a chapter, never by number.
  The x86 book's chapter 8 has 85 pages to the arm64 fork's 87, so every
  numbered chapter-8 override would have unhooked silently. Shared overrides
  moved to `overrides/chNN/<page>.sh`; the arch-bound three (kernel, grub,
  fstab) live under `overrides/arm64/` and `overrides/x86_64/`; `usage`
  (serial console name) and `theend` (release string) read `TUP_ARCH`.
  The driver hands every override its page as `$TUP_PAGE`, so no override
  carries a path with a number in it either.
- `check_overrides.py` and `check_placeholders.py` resolve against every
  extracted book; both pass on both (46/46 hooks, 12/12 placeholders).
- `buildvm/` is the scaffold for a Linux host without Lima or sudo, and
  `buildvm/prepare-host.sh` is the first time chapters 2 to 4 exist in the
  repository as bytes rather than as something typed into a VM.
- `boot_witness.sh` and `release.sh` take `TUP_ARCH`, pick the accelerator
  the host can actually open, and (release) witness an overlay so the
  shipped master is the bytes that were witnessed.
