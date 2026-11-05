# External VM tests for the TUP ISO

Test-host tooling only. Nothing here is installed in TUP, and nothing here is
hardware evidence: the guest is QEMU 8.2 with OVMF under **TCG** (opening
`/dev/kvm` returned ENODEV on the qualified host, and no script switches
accelerator). Every result file says `release_eligible: false`.

**State on 2026-11-05: the SSH kinds have never been run against a VM.** No TUP
ISO existed when this was written. What ran is listed under "What was run".

## Files

| File | Input | A pass establishes | It does not establish |
| --- | --- | --- | --- |
| `uefi.sh` | kind, media file, its SHA256, a new output directory | see the kinds below | anything about real hardware, a real USB stick or another machine on the LAN |
| `remote_check.py` | called by `uefi.sh` for the `*-ssh` kinds | each named check in `RESULT.json` | that the firewall drops non-private sources (every peer is 10.0.2.2) |
| `ventoy-image.py`, `loop_guard.py` | ISO, its SHA256, Ventoy cache, private parted prefix, a named workspace | Ventoy 1.1.18's own installer, at its defaults, made an MBR image whose partition 1 is the exFAT it creates; the ISO was copied onto it through the builder kernel's exfat driver as a non-sparse file (block map: no hole), unmounted, remounted read-only and read back by SHA256 | that the image boots; that a stick written by Windows or macOS behaves the same; that Ventoy2Disk.exe produces the same layout |
| `acquire-ventoy.py`, `ventoy-source.json` | cache directory (downloads over HTTPS) | the archive matches the SHA256 GitHub publishes for release v1.1.18 | a signature: none is published |
| `host-tools.sha256`, `remote-tools.sha256` | none | the emulator, firmware, mtools and OpenSSH client are the bytes these tests were written against | that those builds are correct |
| `private-parted.json` | none | the extracted (never installed) Ubuntu parted packages and files Ventoy's installer is allowed to call | |

`uefi.sh` kinds. All use machine `pc-q35-8.2`, `-nodefaults`, a private copy of
the firmware variables and a serial log; the verdict rule is the sourced
`tup/boot_verdict.sh`, never a copy.

| Kind | Boot device | Network | Pass means |
| --- | --- | --- | --- |
| `host-smoke`, `ventoy-host-smoke` | ide-cd / USB on xhci | none | host-built GRUB printed its marker and QEMU exited 0. Not a TUP test. |
| `tup-iso`, `ventoy-tup`, `installed-disk` | ide-cd / USB on xhci / virtio-blk | none | `tup login:` on ttyS0, 12 s settle, no panic, guest alive |
| `tup-iso-ssh` | ide-cd; enrollment volume (MBR, one FAT32 partition, label `TUP-ENROLL`) on read-only virtio-blk | one forward | the serial verdict **and** every remote check **and** a clean power-off |
| `ventoy-tup-ssh` | the Ventoy image as the only USB storage on xhci; **no second disk** | one forward | the same, reached through Ventoy's menu, with the owner key read from `tup-enroll/authorized_keys` on Ventoy's data partition |

The `*-ssh` kinds default to 2048 MiB and 2 vCPUs (`--memory-mib`, `--cpus`;
the others keep 4096 and 4). Their only network is
`-netdev user,restrict=on,hostfwd=tcp:127.0.0.1:PORT-10.0.2.15:22` on
virtio-net. The QEMU 8.2 manual says of `restrict=on` that the guest "will not
be able to contact the host and no guest IP packets will be routed over the host
to the outside. This option does not affect any explicitly set forwarding
rules." libslirp 4.7.0 answers DHCP before applying the restriction and then
leaves the gateway and DNS options out of the lease, so the guest has
10.0.2.15/24, no default route and no resolver. The QMP socket lives in the
output directory and is used for one thing: `system_powerdown` when the guest
has no sudo.

## The owner flow these tests copy

One stick. The owner installs Ventoy on it, copies the ISO to the top level of
its data partition, and creates a directory `tup-enroll` there holding
`authorized_keys` (and optionally `owner`). The live system's boot hook mounts
that partition read-only at `/run/initramfs/tup-ventoy/media`, and the
enrollment service reads
`/run/initramfs/tup-ventoy/media/tup-enroll/authorized_keys`. `ventoy-image.py`
builds exactly that. Because the machine is headless, nobody can pick a menu
entry, so the image also carries `ventoy/ventoy.json` naming the ISO as
`VTOY_DEFAULT_IMAGE` with a 2 s menu timeout (Ventoy's documented control
plugin). The owner needs the same file, or a monitor and keyboard.

The direct-ISO kind keeps the separate volume: a stick prepared on a Mac would
be one MBR partition holding FAT32, label `TUP-ENROLL`, and that is what
`remote_check.py prepare` builds (128 MiB, so mformat's clusters stay above
FAT32's 65525 floor; `mpartition` makes the table, `mformat -F` the filesystem).
Enrollment on a whole-device FAT filesystem without a partition table is **not
established** by any run, and `RESULT.json` says so.

## Guest assumptions to verify at first boot

The fixtures and checks above rely on these facts about the TUP guest. None has
been observed in a running guest. The kernel configuration in the repository
(`tup/hardware/linux-6.18.60-x86_64.config`) says `=y` for each driver below, which is a
statement about a file and not about the kernel that gets built into the ISO.

- The kernel drivers for `xhci` (`USB_XHCI_HCD`, `USB_XHCI_PCI`), `usb-storage`
  (`USB_STORAGE`) and `exfat` (`EXFAT_FS`) are built in, not modules: nothing
  loads a module before the Ventoy hook looks for the data partition.
- The enrollment path under Ventoy is
  `/run/initramfs/tup-ventoy/media/tup-enroll`, so the key is read from
  `/run/initramfs/tup-ventoy/media/tup-enroll/authorized_keys` on the stick's exFAT
  partition.
- The direct kind (`tup-iso-ssh`) needs `virtio-blk` (the `TUP-ENROLL` volume),
  `virtio-net` (the forwarded SSH port) and `vfat` (that volume's FAT32) in the
  guest kernel as well.

Once a guest runs, check them against `/lib/modules/$(uname -r)/modules.builtin`
(built in) and `/proc/filesystems` (`exfat`, `vfat`), then correct this list from
what is seen.

## Command lines

Variables name private paths outside the repository. `TUP_VM_RUNS` is a
root-owned directory nobody else can write.

Direct ISO boot with the SSH check:

```sh
bash tup/boot/tests-runtime/uefi.sh tup-iso-ssh "$TUP_ISO" "$TUP_ISO_SHA256" \
  "$TUP_VM_RUNS/tup-iso-ssh-01" --ssh-port 2222
```

Ventoy image from a given ISO (root; needs the `exfat` kernel module loaded;
allocates one loop device over a new regular file, mounts only that loop's
partition 1 on a directory inside the output, and detaches; `--size-gib` must
exceed the ISO by 512 MiB). `--generate-test-key` makes an Ed25519 pair in
`OUTPUT/enroll-keys/`, writes its public half to `tup-enroll/authorized_keys`
on the data partition and leaves `ENROLL.json` naming the image digest;
`--authorized-keys FILE` places real public keys instead, but then no SSH test
can log in. `--owner NAME` also writes `tup-enroll/owner`.

```sh
python3 tup/boot/tests-runtime/acquire-ventoy.py --cache "$TUP_VENTOY_CACHE"   # once, network
modprobe exfat
python3 tup/boot/tests-runtime/ventoy-image.py --cache "$TUP_VENTOY_CACHE" \
  --iso "$TUP_ISO" --iso-sha256 "$TUP_ISO_SHA256" --parted-prefix "$TUP_PRIVATE_PARTED" \
  --workspace "$TUP_VM_RUNS" --output "$TUP_VM_RUNS/ventoy-tup-image-01" --size-gib 4 \
  --generate-test-key
```

Ventoy boot with the SSH check (`image_sha256` is in the image's `RESULT.json`;
the owner key pair is read from `enroll-keys` beside the image, or from
`--enroll-keys DIR`, and only if `ENROLL.json` names this image's digest and
the same `--owner`):

```sh
bash tup/boot/tests-runtime/uefi.sh ventoy-tup-ssh "$TUP_VM_RUNS/ventoy-tup-image-01/ventoy.raw" \
  "$TUP_VENTOY_IMAGE_SHA256" "$TUP_VM_RUNS/ventoy-tup-ssh-01" --ssh-port 2223
```

Other options: `--owner NAME` (writes `tup-enroll/owner`; without it the guest
must use its default account `owner`), `--boot-budget` (600 s), `--ssh-wait`
(300 s), `--poweroff-budget` (180 s). The exit status is 0 only for a pass.

### What the Ventoy installer is run with

`Ventoy2Disk.sh -i LOOP`, nothing else. Its own source (`tool/VentoyWorker.sh`,
v1.1.18) states the defaults: `-g` selects GPT "default is MBR", and secure-boot
support is on unless `-S` is given ("default is enabled"). The earlier fixture
passed `-g -S`; this one does not. The resulting layout is checked: MBR, partition
1 at sector 2048 with type 07 and the boot flag, partition 2 type EF and 65536
sectors (VTOYEFI, FAT16), partition 1 `exfat` labelled `Ventoy` by `blkid`.
With secure-boot support on, VTOYEFI's `EFI/BOOT/BOOTX64.EFI` is a 1,045,176-byte
program (Ventoy's shim chain), not the 1,931,696-byte loader the `-S` fixture had.
Whether secure boot is active in the OVMF variables used was not checked, so no
claim is made about secure-boot enforcement. The
Windows installer's defaults were looked up and not established: the 1.1.18
sources for it carry no default for either setting in the files read, and the
documentation page for the Linux script still says secure boot is off by
default, which the script itself contradicts. Treat "same as the Windows
installer" as unverified.

## What a remote run does

1. Generates the keys inside the new output directory. Direct ISO: two Ed25519
   keys and the read-only `TUP-ENROLL` volume holding `tup-enroll/authorized_keys`
   (one key) and optionally `tup-enroll/owner`, read back with mtools and checked
   from its raw bytes (MBR, one FAT32 LBA partition at 1 MiB, label). Ventoy: the
   owner key pair the image was built with is copied in, only the never-enrolled
   key is made, and no enrollment volume exists. The second key is never enrolled.
2. Boots, applies the serial verdict, then runs these checks. Each is recorded
   in `RESULT.json` as pass or fail with its command, exit status and the files
   under `remote/checks/` that hold its output.

| Check | Passes when |
| --- | --- |
| `serial_boot_verdict` | `boot_verdict.sh` says BOOTED |
| `owner_key_login` | within `--ssh-wait`, the owner logs in with the enrolled key (attempts are counted) |
| `known_hosts_created` | that first connection (`accept-new`) wrote exactly one host key |
| `guest_uname`, `guest_id`, `guest_os_release`, `guest_ip_address` | Linux x86_64; a non-root uid with the owner's name; one `ID=tup` and one `VERSION_ID`; the lease 10.0.2.15 |
| `guest_kernel_cmdline` | `cat /proc/cmdline` is not empty and has no `rdinit=/vtoy/vtoy` token (Ventoy's fallback path). The line itself is kept in the detail and the saved output whatever the verdict. Applied to both SSH kinds |
| `guest_system_running` | `systemctl is-system-running --wait` prints `running`; otherwise the failed units and jobs are kept |
| `sudo_probe`, `nft_ruleset_as_root` | the probe ran; with sudo, `sudo -n /usr/sbin/nft list ruleset` lists a table. Without sudo this one check is `not-applicable` and says the firewall was not inspected |
| `second_connection_same_known_hosts` | `StrictHostKeyChecking=yes` succeeds and `known_hosts` is unchanged |
| `changed_host_key_refused` | the same host with a different pinned key ends in "Host key verification failed" |
| `sftp_round_trip_sha256` | 1 MiB put, get and remove; the SHA256 is preserved |
| `root_login_refused`, `unenrolled_key_refused` | the server answers "Permission denied"; a dropped connection does not count |
| `password_authentication_refused` | the server offers neither `password` nor `keyboard-interactive`, and the recorded askpass was never invoked |
| `owner_login_after_refusals` | the owner can log in again within 120 s (sshd penalises a source for failures, and all test traffic shares one source) |
| `poweroff_request`, `guest_powered_off` | `sudo -n systemctl poweroff` by the owner, or QMP `system_powerdown` without sudo; QEMU exits 0 within the budget and the serial log has the kernel's `reboot: Power down` |
| `host_inputs_unchanged` | after QEMU is gone, the media digest and every pinned tool still match; `uefi.sh` runs its cleanup and these rechecks **before** `remote_check.py conclude`, so `RESULT.json` can never say VERIFIED for a run the wrapper then rejects. The recheck output is `host-recheck.txt` |

A missing tool, a timeout, a check that was not reached and a second result in
one directory are failures or refusals, never skips. The private test keys of
the run are deleted when the result is written (the Ventoy image's own
`enroll-keys/owner_key` stays beside the image; it is a throwaway key whose only
use is that image, so delete the directory with it).

## What was run (2026-11-05)

On the Linux builder, as root, TCG, one QEMU at a time, 256 MiB, 1 vCPU, 60 s
budget, nothing listening:

1. `ventoy-image.py` with the real Ventoy 1.1.18 installer at its defaults on a
   loop over a new 1 GiB regular file, then the 7.8 MB host smoke ISO copied to
   the exFAT data partition with `cp --sparse=never`. Result: `iso_extents` 1,
   `iso_holes` 0, from FIBMAP block by block (`filefrag` is kept as well, but
   exfat has no FIEMAP so it only prints "1 extent found" and cannot show a hole
   inside a run); the ISO and `ventoy/ventoy.json` read back with the right
   SHA256 after unmounting and remounting read-only.
2. `uefi.sh ventoy-host-smoke` on that image: **PASSED**. The marker was written
   about 8 s after QEMU started and QEMU had exited by second 9 (`elapsed_seconds:
   9`), status 0, nothing on stderr.
3. Control, the same script on the same day on the earlier ext4 image: **FAILED**
   as before. The marker came at about 18 s, QEMU was still running at 60 s and
   `qemu.stderr` says it was terminated by the wrapper's SIGTERM.

That is a difference between two images, not a proof of one cause: the old image
differs in five ways at once (sparse ISO on ext4, GPT, secure boot off, ISO in a
subdirectory, and a path with spaces). What the pair does show is that the
earlier failure was a property of the fixture and not of the smoke ISO, QEMU or
the script. The passing run is consistent with Ventoy 1.1.18 starting the ISO's
own GRUB, which then powers the machine off by its ACPI write; its serial log
holds only the firmware's boot lines and the marker, so which GRUB printed the
marker and which halt path ran were not observed.

The earlier stored FAILED verdict (`ventoy-host-smoke`, first run) is kept
unchanged; nothing was relabelled and both new results are stored in new
directories.

### Why the first Ventoy smoke failed (read from sources, not observed)

- **Measured** on the earlier fixture (`debugfs stat`, read-only): `mkfs.ext4
  -d` skips all-zero blocks, so the 7,792,640-byte ISO was stored with 9008
  allocated 512-byte blocks and holes at filesystem blocks 3-7. The read-back
  that fixture used (`debugfs dump`) zero-fills holes and so could not see it.
  The fixture was therefore not a stick the owner would make.
- **From the Ventoy 1.1.18 sources, not run:** its modified GRUB 2.04 ext2
  driver `grub_ext_get_file_chunk` returns at the first hole, so
  `ventoy_check_block_list` fails and `vt_img_sector` prints "Unsupported chunk
  list". `grub.cfg` carries on; `ventoy_x64.efi fallback` finds no boot file and
  returns silently; the `# fallback` block runs the ISO's own `grub.cfg` inside
  Ventoy's GRUB 2.04 with `rdinit=/vtoy/vtoy` on the command line. So the marker
  was most likely printed by **Ventoy's** GRUB 2.04, not by the ISO's GRUB 2.14.
- **From the GRUB sources, not run:** in 2.04 `grub_halt` calls
  `grub_machine_fini(GRUB_LOADER_FLAG_NORETURN)`, which reaches
  `grub_efi_memory_fini` and frees every GRUB allocation, including the loaded
  `halt` and `acpi` modules, before `grub_acpi_halt` runs. GRUB 2.14 passes
  `GRUB_LOADER_FLAG_EFI_KEEP_ALLOCATED_MEMORY` to avoid that. That is the most
  likely reason the halt hung. It was not observed (no debug output was taken),
  and the rerun above changes several variables, so it is not isolated either.
- Excluded for this configuration: Ventoy's ACPI-table replacement. Release
  1.1.18's `grub.cfg` sets `VTOY_PARAM_NO_ACPI=1`, so `vt_acpi_param` is skipped.

The TUP-through-Ventoy test does not depend on any of this. `ventoy-tup-ssh`
never asks firmware or GRUB to halt: the boot is judged by the serial prompt and
a real login, and power-off is requested from the running system (the owner's
`systemctl poweroff`, or the ACPI power button through QMP) and performed by the
Linux kernel. The `guest_kernel_cmdline` check now fails a run on Ventoy's
fallback path whatever else passes. `ventoy-host-smoke` keeps its original rule.

## Review notes on the preserved drafts

- `ventoy-image.py` and `loop_guard.py` named the builder's workspace
  literally; the workspace is now a required argument that must be root-owned
  and not writable by others. Argument refusals precede the root check.
- `uefi.sh` refuses an existing output before hashing the media, as well as at
  `mkdir`.
- The fixture no longer writes `VTOY_SECURE_BOOT_POLICY` into `ventoy.json`; it
  is not an option Ventoy 1.1.18's GRUB reads (the retained `grub.cfg` has no
  such variable).
- `loop_guard.check` accepts one extra argument, the `(partition, mountpoint)`
  pair this program mounted itself; any other mount whose source starts with the
  loop's name still refuses, and the wrappers Ventoy calls pass nothing, so for
  them nothing changed.
- The host smoke cannot tell a power-off from a guest reset, because
  `-no-reboot` ends QEMU for both. The `*-ssh` kinds require the kernel's
  `reboot: Power down` line as well.

## Checks

```sh
python3 -m unittest discover -s tup/tests -p 'test_runtime_tools.py' -v
bash -n tup/boot/tests-runtime/uefi.sh
```

The unit tests drive the verdict rules with a scripted client and run
`uefi.sh` end to end against a stand-in that is not QEMU: it prints a prompt and
answers QMP (and, for one test, rebuilds the media while it runs). On the Linux
test host they also build the enrollment image with the real mtools and
ssh-keygen. The population step of `ventoy-image.py` is tested with a recording
runner: the loop is proven before every mount, copy, sync and unmount, the copy
is `--sparse=never`, and a failed copy still unmounts. The parts of `build()`
that need no loop are separate functions with their own tests: `stick_files` (the
file map: `ventoy/ventoy.json` naming the ISO and the menu timeout,
`tup-enroll/authorized_keys`, optional `tup-enroll/owner`), `enroll_record` (the
`ENROLL.json` dictionary; a round trip feeds the writer's output to
`remote_check.adopt_ventoy_keys` on Linux, and a changed image digest, owner or
key fingerprint is refused) and `require_whole_file` (a hole, as in block map
`[30, 0, 32]`, or no extent refuses). They start no VM, loop
device, mount or network listener, and a pass there says nothing about a real
guest.

Sources: [QEMU invocation, `-netdev user`](https://www.qemu.org/docs/master/system/invocation.html),
[QMP specification](https://www.qemu.org/docs/master/interop/qmp-spec.html),
[libslirp 4.7.0 `udp.c`, `tcp_input.c`, `bootp.c`](https://gitlab.freedesktop.org/slirp/libslirp/-/tree/v4.7.0/src),
[ssh_config(5)](https://man.openbsd.org/ssh_config), [sshd_config(5) `PerSourcePenalties`](https://man.openbsd.org/sshd_config),
[mtools manual](https://www.gnu.org/software/mtools/manual/mtools.html),
[GRUB 2.14 `lib/efi/halt.c` and `commands/acpihalt.c`](https://git.savannah.gnu.org/cgit/grub.git/tree/grub-core/lib/efi/halt.c?h=grub-2.14),
[Ventoy 1.1.18 installer, `tool/VentoyWorker.sh`](https://github.com/ventoy/Ventoy/blob/v1.1.18/INSTALL/tool/VentoyWorker.sh),
[Ventoy: using the Linux script and the data partition](https://www.ventoy.net/en/doc_start.html),
[Ventoy 1.1.18 EFI loader](https://github.com/ventoy/Ventoy/blob/v1.1.18/EDK2/edk2_mod/edk2-edk2-stable201911/MdeModulePkg/Application/Ventoy/Ventoy.c)
and [its GRUB commands](https://github.com/ventoy/Ventoy/blob/v1.1.18/GRUB2/MOD_SRC/grub-2.04/grub-core/ventoy/ventoy_cmd.c).
