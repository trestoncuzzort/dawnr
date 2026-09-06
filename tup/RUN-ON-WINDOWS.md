# Run tup on a Windows PC

tup 0.1 is arm64. A Windows lab machine is almost certainly x86_64, and that
rules out the tools you'd reach for first: **VMware Workstation, VirtualBox,
and Hyper-V cannot run an arm64 guest on an x86 host**: they virtualize the
CPU they're on, they don't emulate a different one. The `.vmdk`/`.vdi` files
in the release are for arm hosts and for the future x86_64 tup; on this PC
they will not boot, and that is expected, not a bug.

What does work is **QEMU**, which emulates the CPU. tup's boot is small
enough that emulation is fine: 40 seconds to a login prompt on an Ubuntu
host with no acceleration at all, and 45 seconds on a second Ubuntu
machine booting the released split image reassembled from its parts
(witnessed 2026-08-31). **On Windows it has now been witnessed both ways**,
2026-09-02, Windows 11 Pro on an i9-14900K, same image `5bb06ce1…`, pure
TCG: **21.1 s** to `tup login:` under native QEMU 11.1.0 (Path A) and
**26.9 s** under WSL2's QEMU 8.2.2 (Path B). Both timings include GRUB's 5 s
countdown. The receipts for those two boots are held by the person who ran
them and are not in this repository; what is here is the report of them.

## What to bring

The GitHub release caps assets at 2 GB, so the image ships as TWO parts
that you join back into one file. Download from the `v0.1-witness` release
(or carry on a USB stick): `tup-0.1-arm64.qcow2.part-aa`,
`tup-0.1-arm64.qcow2.part-ab`, and `SHA256SUMS`.

Reassemble and verify, in PowerShell, from the folder holding them:

```powershell
cmd /c copy /b tup-0.1-arm64.qcow2.part-aa+tup-0.1-arm64.qcow2.part-ab tup-0.1-arm64.qcow2
Get-FileHash .\tup-0.1-arm64.qcow2 -Algorithm SHA256
# must equal the tup-0.1-arm64.qcow2 line in SHA256SUMS
```

The `copy /b` matters: `/b` is binary mode. Do not try to join the parts
with `Get-Content` unless you know to pass `-AsByteStream`; the default
text mode silently corrupts a binary file.

## Path A: QEMU for Windows (native)

1. Install QEMU from https://qemu.weilnetz.de/w64/ (the standard Windows
   build). Needs admin rights once.
2. The UEFI firmware tup needs ships **inside that install**:
   `C:\Program Files\qemu\share\edk2-aarch64-code.fd`.
3. From PowerShell, in the folder holding the image:

```powershell
& "C:\Program Files\qemu\qemu-system-aarch64.exe" `
  -machine virt -cpu cortex-a72 -m 2048 -smp 2 `
  -drive if=pflash,format=raw,readonly=on,file="C:\Program Files\qemu\share\edk2-aarch64-code.fd" `
  -drive file=tup-0.1-arm64.qcow2,format=qcow2,if=virtio `
  -nographic
```

The console runs in that terminal. `tup login:` is the finish line; log in
as `root` with password **`tup`** and change it. `login` times out after
60 s at the prompt. To quit QEMU: `Ctrl-a` then `x`.

If you script the launch instead of typing it: PowerShell's
`Start-Process -ArgumentList @(...)` does not re-quote the space in
`Program Files`, and QEMU dies within a second with no output (measured
2026-09-02). The direct `& "..."` call above is fine; only a launcher that
rebuilds the argument list hits it.

One caution, measured on Ubuntu 2026-08-31: this command attaches the disk
read-write and the guest touches the filesystem on every boot, so after
one boot the qcow2 no longer matches its published digest. If you care
about keeping the verified bytes verified, either add `-snapshot` to the
command above (all changes are discarded at exit), or boot an overlay and
leave the reassembled master untouched:

```powershell
& "C:\Program Files\qemu\qemu-img.exe" create -f qcow2 -b tup-0.1-arm64.qcow2 -F qcow2 work.qcow2
# then boot work.qcow2 instead of the master
```

## Path B: WSL2 (if the machine has it)

Inside a WSL2 Ubuntu, the machine *is* an Ubuntu host, so follow
[`RUN-ON-UBUNTU.md`](RUN-ON-UBUNTU.md) verbatim (`sudo apt-get install
qemu-system-arm qemu-efi-aarch64`, one command, done). Measured 26.9 s on
2026-09-02 (QEMU 8.2.2 from apt, pure TCG, `-accel help` lists tcg only).

## What you are looking at, once it boots

Same checks as everywhere: `cat /etc/os-release` says `NAME="tup"`;
`claude --version` answers from the agent layer (2.1.251 as shipped); every
file on the disk is accounted for in the repo's `receipts/`, the one
inventory that describes this image is named in `receipts/INVENTORIES.md`.
What is *not* in the image (no `curl`, `wget`, `git`, `unzip`, `which`) and
how to get a file in anyway is in `RUN-ON-UBUNTU.md`.

## Record the witness

tup has booted on one Windows machine (above). A second one is still
worth keeping: note the Windows version, QEMU version, path A or B, and
time-to-login, and drop it in `receipts/` as
`boot-witness-windows-<date>.txt` (a photo of the login prompt is a fine
start). The house rule is that claims are measured: "boots on Windows"
became true the moment someone wrote down that it did, and stays exactly as
true as the receipts that exist.
