# System configuration and owner enrollment

This chapter turns the built root into a machine that can be reached: wired
DHCP networking, name resolution, a firewall that is loaded before the network,
and SSH for one owner who enrolls a public key from the boot media. The image
itself stays generic. It contains no host key, no account, no owner key and no
enrollment; the root account stays locked and nothing has a default password.

**Status: tested and rehearsed, not booted.** The pages and the enrollment step
have run only against fixtures and in a rehearsal chroot made of the build
host's binaries. The layer runner has not run them, and no TUP kernel has
started these units. What ran is listed under [Evidence](#evidence); what must
be checked on the first real boot is listed under
[First boot checks](#first-boot-checks).

## Enrolling from a MacBook

1. On the Mac, create a key if you do not have one. Accept the default file
   and choose a passphrase:

   ```sh
   ssh-keygen -t ed25519
   ```

2. Plug in the Ventoy USB stick that holds the TUP ISO and copy the **public**
   key (the `.pub` file) into a folder named `tup-enroll`, as a file named
   exactly `authorized_keys`:

   ```sh
   mkdir /Volumes/Ventoy/tup-enroll
   cp ~/.ssh/id_ed25519.pub /Volumes/Ventoy/tup-enroll/authorized_keys
   ```

   The volume is named `Ventoy` unless it was given another label when the
   stick was made; the folder goes at its top level, beside the ISO files.
   Eject the stick. Never copy `id_ed25519` (without `.pub`): that is the
   private key, and enrollment refuses it.

3. Connect the desktop to the router with an Ethernet cable and boot it from
   the stick.

4. Read the console (a monitor on the desktop, or its serial port). Above the
   login prompt it shows the addresses and one of two states:

   ```
   TUP owner access: ENROLLED. Account owner, scope private-networks.
     Connect from the home network:  ssh owner@tup.local
     ED25519 host key fingerprint:  SHA256:...
   ```

   or `NOT ENROLLED`, with the reason for the last refusal if there was one.

5. On the Mac:

   ```sh
   ssh owner@tup.local
   ```

   `ssh` prints the host key fingerprint the first time. Type `yes` only if it
   is the same as the one on the console. If `tup.local` does not resolve, use
   the IPv4 address shown on the console. If the connection hangs instead, the
   router probably hands out public IPv6 addresses, which the firewall does not
   admit: use `ssh -4 owner@tup.local` or the IPv4 address.

Only plain `ssh-ed25519` public keys are accepted, one to eight lines. Options
in front of a key, other key types and private keys are refused, and a refusal
enrolls nothing. Files that macOS adds beside yours (`._authorized_keys`,
`.DS_Store`) are ignored.

Optional files in the same folder:

| File | Meaning |
| --- | --- |
| `owner` | One line: the account name instead of `owner`. |
| `listen` and `peer` | One IP address per line, both files together. Selects the exact scope: sshd binds only the `listen` addresses and the firewall admits only the `peer` addresses. Meant for an installed system; see [Not covered](#not-covered) for a live boot. |
| `clock` | One line, the word `utc`: the hardware clock of this machine holds UTC, so time synchronization may run. See [The hardware clock](#the-hardware-clock) before adding it on a machine that also boots Windows. |

Instead of the Ventoy stick, a filesystem labelled `TUP-ENROLL` with a
`tup-enroll` folder works, for example a second USB stick formatted in Disk
Utility as MS-DOS (FAT) or ExFAT with that name. It is mounted read-only and
has priority. A stick formatted as APFS or Mac OS Extended cannot be read.

### The hardware clock

Windows keeps local time in the hardware clock; Linux expects UTC there. Once
a Linux system has synchronized its clock over the network, the kernel copies
the time back to the hardware clock, as UTC, about every eleven minutes, and
Windows then shows a time that is wrong by the local UTC offset until its own
clock is set again. To avoid changing a clock that Windows relies on, **time
synchronization is off until the owner says the hardware clock is in UTC**.
Until then TUP reads the hardware clock as if it were UTC and never writes it,
so its own time is off by that same offset: fine for SSH, but timestamps are
wrong and a few TLS connections may fail.

There are two ways to get correct time:

- Make Windows keep UTC in the hardware clock (the documented registry value
  `RealTimeIsUniversal`), then put a file named `clock` containing `utc` in
  the `tup-enroll` folder. This is the arrangement that keeps both systems
  right.
- Or accept that Windows will show the wrong time after each TUP session and
  add the same `clock` file.

On an enrolled system the same effect comes from
`sudo touch /etc/tup/hardware-clock-utc` followed by
`sudo systemctl restart systemd-timesyncd`. A hardware clock in local time
with TUP set to the matching time zone is not implemented.

### What the owner account is

The account has no password (`*` in `/etc/shadow`): it can be entered only with
an enrolled key. Where sudo is installed, enrollment adds
`/etc/sudoers.d/10-tup-owner` granting it every command without a password.
**Whoever holds an enrolled private key is therefore root on this machine.**
Keep the key on the Mac and protect it with a passphrase. If sudo is not
installed the marker records `"sudo": "absent"` and the owner has no route to
root, because root itself is locked.

### Limits to know before the first boot

- **A live boot forgets.** Booted from the ISO, nothing written to `/etc`
  survives a reboot. Enrollment is applied again from the stick on every boot
  and a new host key is generated every time, so from the second boot `ssh`
  warns that the host identification changed. Remove the old entry with
  `ssh-keygen -R tup.local` and compare the new fingerprint with the console
  again. Persistent host identity needs an installed system.
- **Enrollment happens once.** On a persistent root, a second boot with the
  marker present changes nothing, even if the files on the stick changed. Key
  rotation and revocation are not implemented.
- **The whole home network can reach port 22.** In the default scope the
  firewall admits SSH from private address ranges and sshd admits only the
  enrolled key. This is meant for a machine behind a home router. The ranges
  include `100.64.0.0/10`, which some providers use on their own network: do
  not connect the machine directly to such a line.
- **Wi-Fi is not configured.** Only wired Ethernet comes up.

## Installing to a disk

The live system can install itself onto one internal disk. Root is locked, so
this is done as the enrolled owner with `sudo`. The installer is
[`install/disk.py`](../install/disk.py), shipped as `/usr/sbin/tup-install`; the
details, every refusal and the tests are in [`../install/README.md`](../install/README.md).
**It has never run on a real disk, only against fakes and regular files; try it in a VM first.**

1. Find the disk by its serial number, never by its name, and check its size:

   ```sh
   lsblk -dno PATH,SERIAL,SIZE,MODEL,TRAN
   ```

2. Make a plan. This only reads: it writes `plan.json` and prints a summary. To have the
   installed system enroll you without the USB stick, give it a folder that holds your
   `authorized_keys` (and `owner`, `listen`, `peer`, `clock` if you use them, nothing
   else; macOS's `.DS_Store` and `._*` files are ignored and listed):

   ```sh
   sudo tup-install plan --target /dev/nvme0n1 --source /run/rootfsbase --output ~/plan.json \
       --enroll-input ~/enroll-in --state /var/tmp/install-state
   ```

3. **Read the summary.** It names the disk by model, serial, WWN and size, shows the new
   layout (a 512 MiB EFI partition, the rest ext4), what will be erased, the disks this
   system is using (never written), the account and key fingerprint that will be enrolled,
   and whether the state directory is in RAM. It ends with `Confirmation token: SERIAL-XXXXXXXX`.
   If anything differs from what you expect, stop: nothing has been written yet.

4. Apply it, typing the token. Start it detached, so that a dropped SSH session (a sleeping
   laptop, Wi-Fi) cannot interrupt it half way through the copy, and follow its log:

   ```sh
   sudo setsid -f tup-install apply --plan ~/plan.json --confirm SERIAL-XXXXXXXX \
       --state /var/tmp/install-state > ~/apply.log 2>&1
   tail -f ~/apply.log
   ```

   `setsid -f` gives the installer its own session, so the hangup of a dropped SSH session
   does not reach it; your shell opens `~/apply.log`, so the log is in your home. The log
   stays empty until the installer ends, then holds `installed ...: receipt ...` or the
   reason it refused (press Ctrl-C to stop following; the install goes on). The progress is
   in `/var/tmp/install-state/PROGRESS.jsonl` (`sudo tail -f` it). Expect the summary of
   step 3 to call the state directory VOLATILE: the live system's root is a RAM overlay and
   there is no persistent storage to give it, so the intent record and journal do not
   survive a reboot, and after a power cut only the disk itself shows that a write started.
   Run in the foreground instead, a dropped session is converted into an interruption: the
   installer finishes the `cp` or `mkfs` it is in, unmounts and stops with the disk
   half-written, and you need a new plan. (This command line has not been run on the image;
   the VM plan in [`../install/README.md`](../install/README.md) is the first run.)
   Apply checks the disk against the plan, writes the partition table, formats, copies the
   system, adds the boot files and verifies the result. Before the first write it looks at
   the disk once more and refuses if anything changed. An interrupted run is never resumed:
   make a new plan (with `--allow-existing`, which then lists what the failed run left).

5. Power off, remove the USB stick and choose the new disk in the firmware boot menu. The
   installer writes no firmware variable, so the firmware's own boot order decides.

**What is refused.** A disk that holds data needs `--allow-existing`, and the summary then
lists what will be destroyed. A disk with no table and no signature is treated as empty only
if its first and last megabyte are all zero bytes; Windows reporting a disk as RAW says
nothing about that. **A disk that looks like Windows is never erased, with or without any
flag**: an NTFS, BitLocker, ReFS or exFAT signature, a Windows dynamic or Storage Spaces
volume, or a Microsoft basic data, reserved or recovery partition makes `plan` and `apply`
refuse. Such a disk must be cleared by you by other means first, so a mistyped `--target`
cannot reach the Windows SSD. The same holds for a disk with a protective MBR but no
readable GPT (a damaged GPT hides what the disk holds), and for a `--state` directory or
`plan --output` file on the target, on such a disk or on an NTFS, exFAT or FAT filesystem.
Also refused: the disk this system booted from or runs on, a
partition, a mounted or swapped-on disk, a disk without a serial number, a disk too small, an
unreadable enrollment input, and an enrollment input that the installed system would refuse
at its first boot. The first boot of the installed system enrolls you from
`/etc/tup/enroll-input` exactly as it would from a stick, and creates a new machine ID and new
SSH host keys.

## What happens at boot

| Unit | Ordered | What it does |
| --- | --- | --- |
| `tup-enroll.service` | after local filesystems, before the units below | Skipped when `/etc/tup/owner-enrolled.json` exists. Waits at most five seconds for a filesystem labelled `TUP-ENROLL`, mounts it read-only at `/run/tup-enroll`, then runs `enroll.py`. No input is a normal boot. A refusal fails this unit only. |
| `tup-firewall.service` | before `network-pre.target` | `nft -f /etc/tup/firewall.nft`, enrolled or not. |
| `tup-sshd.service` | after the firewall | Starts only if the marker exists (`ConditionPathExists`) and the firewall unit is active (`Requires`). |
| `tup-console-status.service` | before `getty-pre.target` | Writes `/run/issue.d/50-tup.issue`, which agetty prints above the login prompt. |
| `systemd-networkd`, `systemd-resolved` | after the firewall | DHCP on every physical Ethernet link, DNS, the Multicast DNS name `tup.local`. |
| `systemd-timesyncd` | after enrollment | Starts only if `/etc/tup/hardware-clock-utc` exists (`ConditionPathExists` in a drop-in). |

`enroll.py` searches, in this order, `/run/tup-enroll/tup-enroll`,
`/run/initramfs/tup-ventoy/media/tup-enroll` (the Ventoy data partition that
holds the ISO file, where [`boot/ventoy-live.sh`](../boot/ventoy-live.sh)
leaves it mounted read-only), `/run/initramfs/isoscan/tup-enroll` (where
dracut's own ISO scan would leave it), `/run/initramfs/live/tup-enroll` and
`/etc/tup/enroll-input` (inside an installed root, for an installer that
copies its input there). The first directory that
contains `authorized_keys` is the input; an invalid input is refused, not
skipped in favour of the next. It then

1. validates every file with `policy.py` and `firewall.py` and renders the
   configuration; refuses if an account, group or home directory of that name
   exists, if a destination is a symbolic link, or if `/`, `/etc`, `/etc/ssh`
   or `/etc/tup` is writable by anyone but root. Up to here nothing changed;
2. writes the new files beside their destinations, generates host keys with
   `ssh-keygen -A`, and checks the staged files with the real tools:
   `sshd -T -f` through `policy.check_effective`, `visudo -cf`, `nft -c -f`,
   and then loads the staged firewall for real with `nft -f`, so a table the
   kernel will not commit stops enrollment while no account exists;
3. creates the account with `useradd` and renames the files into place;
4. writes the marker last, with fsync and rename. It records the scope, the
   input location, key fingerprints and the SHA256 of every installed file.

A failure in step 2 removes the staged files; `tup-firewall.service` runs after
this unit and loads the installed default table again. A failure in step 3 or
4 leaves no marker, so sshd does not start, but the account may already exist;
on a persistent root the next attempt then refuses because it never adopts an
existing account. That state needs repair from an installer or rescue
environment. On a live boot a reboot is enough.

The default `/etc/tup/firewall.nft` is the private-networks table without its
two SSH accept rules: inbound is dropped except loopback, ICMP, DHCP replies,
established traffic and Multicast DNS from private sources.

## What the pages configure

| Page | Files | Source |
| --- | --- | --- |
| `01-identity.sh` | `/etc/os-release` (`ID=tup`, `VERSION_ID=13.1`), `/etc/hostname` (`tup`), `/etc/locale.conf` (`C.UTF-8`), `/etc/profile`, `/etc/inputrc`, `/etc/shells`, a drop-in that keeps boot messages on tty1, and `/etc/modprobe.d/tup-graphics.conf` (`blacklist amdgpu`: the module is built but none of its firmware is staged, so it must not take the screen away from the firmware framebuffer on its own) | LFS 13.1-systemd [11.1](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter11/theend.html), [9.2](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/network.html), [9.7](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/locale.html), [9.8](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/inputrc.html), [9.9](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/etcshells.html), [9.10](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/systemd-custom.html); the book's blocks are copied verbatim and a test compares them |
| `02-network.sh` | `20-wired.network` (`Kind=!*`, `Type=ether`, `DHCP=yes`, `MulticastDNS=yes`, `ClientIdentifier=mac`), a resolved drop-in (`MulticastDNS=yes`, `LLMNR=no`), the `/etc/resolv.conf` stub link, journal size limits, `systemd-networkd-wait-online --any --timeout=30`, and the `systemd-timesyncd` drop-in that makes it wait for `/etc/tup/hardware-clock-utc` | [9.2](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/network.html); systemd 261.2 `network/89-ethernet.network.example`; [systemd.network](https://www.freedesktop.org/software/systemd/man/latest/systemd.network.html), [resolved.conf](https://www.freedesktop.org/software/systemd/man/latest/resolved.conf.html), [journald.conf](https://www.freedesktop.org/software/systemd/man/latest/journald.conf.html), [systemd-networkd-wait-online](https://www.freedesktop.org/software/systemd/man/latest/systemd-networkd-wait-online.service.html) |
| `03-access.sh` | `/usr/lib/tup/remote/{policy,firewall,enroll}.py`, the four units, `/etc/tup/firewall.nft`, `/etc/issue`; enables the units and networkd, resolved and timesyncd with `systemctl --root=/`; asserts the generic final state | [agetty(8)](https://man7.org/linux/man-pages/man8/agetty.8.html) of util-linux 2.42.4, [systemctl(1)](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html) |
| `04-installer.sh` | `/usr/lib/tup-installer/tup/{install/disk.py,boot/__init__.py,boot/inputs.py}` (0755 for the script, 0644 for the modules) and the wrapper `/usr/sbin/tup-install`, which runs `python3 -I -B` on that explicit path; nothing is enabled or started | [`../install/README.md`](../install/README.md); [dosfstools](https://www.linuxfromscratch.org/blfs/view/13.1-systemd/postlfs/dosfstools.html) and [GRUB](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/grub.html) pages for the programs it needs |

`ClientIdentifier=mac` is there because the image ships an empty machine-id and
a live boot generates a new one each time. A machine-id based DHCP identifier
would then change on every boot, and with it the address the router hands out.

`03-access.sh` first refuses a root that lacks any program the units start, or
`/etc/protocols`: nft looks up `ipv6-icmp` by name, and without that file the
firewall table does not load. Where sudo is already installed it also refuses a
`/etc/sudoers` that does not include `/etc/sudoers.d`, because the owner's
sudo rule would then have no effect. It runs the installed renderers with the
target's own Python and
refuses if `tup-sshd.service`, `tup-firewall.service` or the default firewall
differ from what they emit. It ends by asserting the conditions the packager's
`boot/inputs.py check_offline_root()` needs from this chapter: empty
`/etc/machine-id`, no SSH host keys, exactly one locked root entry, a regular
`/etc/os-release` with one `ID=tup` and one `VERSION_ID`, an empty or
comment-only `/etc/fstab`, and no owner key, marker, sudo rule or login
account. `/dev`, `/run` and `/tmp` are the runner's own mounts inside the
chroot and remain the packager's check.

`04-installer.sh` first refuses a root that lacks any program the installer
runs (`sfdisk lsblk blkid wipefs blockdev findmnt udevadm mount umount mkfs.ext4
e2fsck mkfs.fat fsck.fat grub-mkstandalone grub-script-check cp sync python3`; `partx` is not used),
`/usr/lib/grub/x86_64-efi` or one of the GRUB modules the installed menu loads. It
installs the three files, writes the wrapper, and runs the installed copy once
with the target's own Python: it must import from `/usr/lib/tup-installer`, find every
tool, load `enroll.py` from `/usr/lib/tup/remote`, and generate a boot menu that the
target's `grub-script-check` accepts and that the target's `grub-mkstandalone` turns
into an EFI image (temporary files only). It ends by checking that no bytecode
exists beside the installer or the renderers and repeating the assertions of
`03-access.sh` that a page adding files under `/usr` could break (empty machine-id,
no host keys, no enrollment, a comment-only fstab). `dosfstools` (`mkfs.fat`,
`fsck.fat`) comes from the boot chapter, page `04-dosfstools.sh`.

The console text relies on agetty 2.41 or later reading `/run/issue.d/*.issue`
after `/etc/issue` whether or not the latter exists, and on its `\4` and `\6`
escapes, which follow address changes. Both were read in the 2.42.4 manual and
`agetty.c`.

## Evidence

Run on 2026-11-05, on Windows (Python 3.13) and on the Ubuntu 24.04 builder
(Python 3.12, systemd 255):

- The unit tests in `tests/test_remote_policy.py`, `test_remote_firewall.py`,
  `test_remote_enroll.py` and `test_system_pages.py`. Enrollment is exercised
  against a temporary root with every external command replaced by a fixture;
  22 deliberate defects in a copy of the code each made a test fail.
- `bash -n` on the three pages, and `systemd-analyze verify` on the four units
  in a temporary root with stub executables, including three damaged units
  that it must reject.
- The authenticated OpenSSH 10.6p1 host build accepted the private-networks
  configuration with `sshd -T`, printed `ListenAddress 0.0.0.0:22` and
  `ListenAddress [::]:22`, and `policy.check_effective` accepted that output in
  the private-networks scope and refused it in the exact scope.
- The authenticated nftables 1.1.7 host build accepted the exact,
  private-networks and unenrolled tables with `nft -c -f` (check mode, nothing
  loaded) and rejected a damaged one.
- The exact `useradd` arguments, run by Ubuntu's shadow 4.13 against a prefix
  directory, produced a `*` shadow field, `/bin/bash` and a user group.
  Ubuntu's visudo 1.9.15 accepted the sudo rule and rejected a damaged one.
- A rehearsal in a plain chroot without mounts, built from the builder's own
  Ubuntu binaries ([receipt](evidence/rehearsal-20261105.json)). With the
  driver's environment the three pages exited 0, twice;
  `check_offline_root()` accepted the result; `03-access.sh` refused 14
  altered roots and accepted two harmless ones. In the same chroot `enroll.py`
  ran with its default command runner and real tools (useradd, the OpenSSH
  10.6p1 `ssh-keygen -A` and `sshd -T`, visudo, nft in check mode): it created
  the account, installed the files with the expected modes and a marker whose
  hashes match, changed nothing on a second run, and refused an RSA key, an
  injected extra listener and a root without `/etc/protocols` without creating
  an account. The firewall load was recorded and not performed there.

Not run: the pages in the real layer runner, any of this on TUP's own Python
3.14, systemd 261, util-linux 2.42.4, shadow 4.20.2 or OpenSSH and nftables
builds, a unit start, the `TUP-ENROLL` wait and mount, a boot, DHCP, Multicast
DNS, a login, and the firewall against real traffic in this scope.

## First boot checks

- `systemctl --failed` is empty with and without enrollment input, and
  `systemd-analyze verify` accepts the four units on systemd 261.
- `nft list table inet tup_host` shows the table before any address is
  configured; without input nothing listens on port 22. The kernel needs
  nf_tables with conntrack, limit, counter and interval-set support for it.
- The export passes `check_offline_root()`. The book's D-Bus page links
  `/var/lib/dbus/machine-id` to `/etc/machine-id`; the check accepts exactly
  that link and nothing else there, and this chapter does not touch it.
- Under Ventoy the initramfs leaves the stick's data partition mounted
  read-only at `/run/initramfs/tup-ventoy/media` after the switch to the real
  root, and the kernel can mount FAT and exFAT.
- Without the `clock` input `systemd-timesyncd` shows an unmet condition, not
  a failed unit, and the hardware clock keeps Windows' local time across a
  session (`hwclock --show`, then the time Windows shows after the next
  restart). With it, time synchronizes.
- `/` and `/etc` on the live overlay are root-owned and not group-writable
  (sshd `StrictModes` and the enrollment preflight both require it).
- The console shows the state, an address through `\4`, and a fingerprint
  equal to the one `ssh` prints on the Mac.
- `ssh owner@tup.local` works; password login and root login are refused;
  `sudo -n true` works when sudo is installed.
- `sudo tup-install plan --help` prints the usage, no `__pycache__` appears under
  `/usr/lib/tup-installer`, and a plan for a scratch disk in a VM runs as described in
  [`../install/README.md`](../install/README.md) (the page's own check ran only in the
  layer runner's chroot, if at all; see that file for what has been shown).

## Not covered

- Exact scope on the boot that applies it: the unit already loaded by systemd
  does not wait for `network-online.target`. If the listen address is assigned
  later than sshd's five restart attempts (about 25 seconds), sshd stays down
  until the next boot. Enrollment installs an override unit that waits, which
  takes effect from the following boot of a persistent root. Prefer the
  default scope on a live boot.
- A hardware clock kept in local time with a matching time zone in TUP. The
  only supported choices are an unsynchronized system (the default) and a
  hardware clock in UTC; see [The hardware clock](#the-hardware-clock).
- Host key persistence on a live boot, key rotation, revocation, more than one
  owner, Wi-Fi, and any overlay or VPN.
