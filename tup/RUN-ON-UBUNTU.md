# Run tup on Ubuntu

Verified 2026-08-31 on Ubuntu 24.04: **40 seconds to `tup login:` under pure
TCG emulation**: no KVM, no nested virtualization, no special hardware. On a
host with KVM it is faster; without one it still works, and that claim is
measured, not hoped.

## 1. Install QEMU (the only prerequisite)

```sh
sudo apt-get install qemu-system-arm qemu-efi-aarch64
```

No sudo on the box? The previous revision of this file claimed conda-forge
ships QEMU; **it does not** (measured 2026-08-31 on the lab Dell: conda-forge
has no `qemu-system-*` package for linux-64 at all, only user-mode
`qemu-execve-*`). The witnessed no-sudo route is to build it, which conda-forge
*can* supply the build deps for:

```sh
micromamba create -y -n qemubuild -c conda-forge glib pixman meson ninja pkg-config zlib libslirp
curl -LO https://download.qemu.org/qemu-10.1.3.tar.xz   # sha256 fbaa7a0d7a9a1deb…
tar xf qemu-10.1.3.tar.xz && cd qemu-10.1.3
ENV=$(micromamba env list | awk '/qemubuild/{print $NF}')
micromamba run -n qemubuild env PKG_CONFIG_PATH=$ENV/lib/pkgconfig \
  ./configure --prefix=$HOME/.local/opt/qemu-10.1.3 --target-list=aarch64-softmmu \
  --disable-docs --extra-ldflags="-Wl,-rpath,$ENV/lib"
micromamba run -n qemubuild make -j"$(nproc)" -C build && micromamba run -n qemubuild make -C build install
```

Everything below is identical except the firmware path, which becomes
`~/.local/opt/qemu-10.1.3/share/qemu/edk2-aarch64-code.fd` (QEMU bundles its
own EDK2 blobs). Witnessed on ubuntu-box 2026-08-31:
`receipts/boot-witness-dell-20260831T181531Z.txt`.

## 2. Get the image

`tup-0.1-arm64.qcow2` is a compressed qcow2 of the whole system: kernel, GRUB,
the base built from source with a receipt per page, and the agent layer
(Claude Code preinstalled, its exact cost recorded in
`receipts/LAYER-agent-FULL.md`). `SHA256SUMS` ships beside it; check it:

```sh
sha256sum -c SHA256SUMS
```

## 3. Boot it

```sh
qemu-system-aarch64 -machine virt -cpu cortex-a72 -m 2048 -smp 2 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/AAVMF/AAVMF_CODE.fd \
  -drive file=tup-0.1-arm64.qcow2,format=qcow2,if=virtio \
  -nographic
```

On an arm64 host with KVM, add `-accel kvm` and change `-cpu cortex-a72` to
`-cpu host`. On x86_64 (the lab Dell) leave the command exactly as written,
it emulates, and tup's boot is small enough that this is fine.

Log in as `root`, password **`tup`**, which the build sets
(`overrides/29-shadow.sh`), the README says so, and this file used to say
"no password", which cost a reader three `Login incorrect`s on 2026-09-02.
Change it at first boot. `login` gives up after 60 s at the prompt and
returns to `tup login:`; a scripted console has to answer within that. To
exit QEMU from `-nographic`: `Ctrl-a x`.

**The command above writes to the qcow2**: the guest remounts rw and touches
the filesystem on every boot, so your image immediately stops matching
`SHA256SUMS` (measured 2026-08-31: one boot changed the file's size and
digest). If you care about keeping the verified bytes, boot an overlay and
leave the master pristine:

```sh
qemu-img create -f qcow2 -b tup-0.1-arm64.qcow2 -F qcow2 work.qcow2
# then boot work.qcow2 instead; or add -snapshot to the command above
```

Note what is *not* in that command: no `-kernel`, no `-initrd`, no `-append`.
QEMU provides firmware and a disk, nothing else. Everything that executes
after the firmware hands off, GRUB and kernel and init and the login prompt, comes
off tup's own disk. That is the acceptance test the build was driven toward,
and `receipts/boot-witness-*.txt` records it being met.

## 4. What you are looking at

- `cat /etc/os-release`: NAME="tup"
- `claude --version`: the agent layer; the full file-level cost of installing
  it is `receipts/LAYER-agent-FULL.md` (4,844 files added, 1 modified, and the
  one modification is listed)
- `receipts/` in the repo, a receipt for every one of the 105 book pages the
  system was built from, plus the inventories. There are thirteen
  `INVENTORY-*.txt` files and only one describes this image; which one, and
  what the other twelve are, is in `receipts/INVENTORIES.md`. Seven of them
  list Lean under `/opt`, and this image has no Lean: those are the prove and
  train layers being built *after* the release was cut, not this disk.

## What is not in the image

No `curl`, `wget`, `git`, `unzip`, or `which` (measured against the
inventory and inside a booted guest, 2026-09-02). `command -v` does what
`which` did. The image has `python3` (3.14, not the 3.12 the `t` docs
assume) with `ssl`, plus `tar` and `zstd`, and QEMU's user-mode network puts
the host at `10.0.2.2`; so the witnessed way to move a file in is an HTTP
server on the host and `python3 -c 'import urllib.request ...'` in the guest.
Fetching tools belong in a layer with a receipt, not in a base that is
supposed to be able to say what it contains.

## What this is not, yet

- Not x86_64-native: the image is arm64 and emulates on x86 hosts. A native
  x86_64 build through the same driver and receipts is planned.
- Not verified on VMware/Hyper-V: the kernel carries SATA/e1000 fallbacks that
  should boot there, but nobody has witnessed it. Anything unwitnessed is
  labeled as such, which is the house rule.
