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
   the IPv4 address shown on the console.

Only plain `ssh-ed25519` public keys are accepted, one to eight lines. Options
in front of a key, other key types and private keys are refused, and a refusal
enrolls nothing. Files that macOS adds beside yours (`._authorized_keys`,
`.DS_Store`) are ignored.

Optional files in the same folder:

| File | Meaning |
| --- | --- |
| `owner` | One line: the account name instead of `owner`. |
| `listen` and `peer` | One IP address per line, both files together. Selects the exact scope: sshd binds only the `listen` addresses and the firewall admits only the `peer` addresses. |

Instead of the Ventoy stick, any filesystem labelled `TUP-ENROLL` with a
`tup-enroll` folder works, for example a second USB stick. It is mounted
read-only and has priority.

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

## What happens at boot

| Unit | Ordered | What it does |
| --- | --- | --- |
| `tup-enroll.service` | after local filesystems, before the three units below | Skipped when `/etc/tup/owner-enrolled.json` exists. Waits at most five seconds for a filesystem labelled `TUP-ENROLL`, mounts it read-only at `/run/tup-enroll`, then runs `enroll.py`. No input is a normal boot. A refusal fails this unit only. |
| `tup-firewall.service` | before `network-pre.target` | `nft -f /etc/tup/firewall.nft`, enrolled or not. |
| `tup-sshd.service` | after the firewall | Starts only if the marker exists (`ConditionPathExists`) and the firewall unit is active (`Requires`). |
| `tup-console-status.service` | before `getty-pre.target` | Writes `/run/issue.d/50-tup.issue`, which agetty prints above the login prompt. |
| `systemd-networkd`, `systemd-resolved`, `systemd-timesyncd` | after the firewall | DHCP on every physical Ethernet link, DNS, the Multicast DNS name `tup.local`, time. |

`enroll.py` searches, in this order, `/run/tup-enroll/tup-enroll`,
`/run/initramfs/isoscan/tup-enroll` (the USB filesystem that holds the ISO
under Ventoy) and `/run/initramfs/live/tup-enroll`. The first directory that
contains `authorized_keys` is the input; an invalid input is refused, not
skipped in favour of the next. It then

1. validates every file with `policy.py` and `firewall.py` and renders the
   configuration; refuses if an account, group or home directory of that name
   exists, if a destination is a symbolic link, or if `/`, `/etc`, `/etc/ssh`
   or `/etc/tup` is writable by anyone but root. Up to here nothing changed;
2. writes the new files beside their destinations, generates host keys with
   `ssh-keygen -A`, and checks the staged files with the real tools:
   `sshd -T -f` through `policy.check_effective`, `visudo -cf`, `nft -c -f`;
3. creates the account with `useradd`, renames the files into place, loads the
   firewall with `nft -f`;
4. writes the marker last, with fsync and rename. It records the scope, the
   input location, key fingerprints and the SHA256 of every installed file.

A failure in step 2 removes the staged files and leaves the default firewall in
place. A failure in step 3 or 4 leaves no marker, so sshd does not start, but
the account may already exist; on a persistent root the next attempt then
refuses because it never adopts an existing account. That state needs repair
from an installer or rescue environment. On a live boot a reboot is enough.

The default `/etc/tup/firewall.nft` is the private-networks table without its
two SSH accept rules: inbound is dropped except loopback, ICMP, DHCP replies,
established traffic and Multicast DNS from private sources.

## What the pages configure

| Page | Files | Source |
| --- | --- | --- |
| `01-identity.sh` | `/etc/os-release` (`ID=tup`, `VERSION_ID=13.1`), `/etc/hostname` (`tup`), `/etc/locale.conf` (`C.UTF-8`), `/etc/profile`, `/etc/inputrc`, `/etc/shells`, and a drop-in that keeps boot messages on tty1 | LFS 13.1-systemd [11.1](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter11/theend.html), [9.2](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/network.html), [9.7](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/locale.html), [9.8](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/inputrc.html), [9.9](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/etcshells.html), [9.10](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/systemd-custom.html); the book's blocks are copied verbatim and a test compares them |
| `02-network.sh` | `20-wired.network` (`Kind=!*`, `Type=ether`, `DHCP=yes`, `MulticastDNS=yes`, `ClientIdentifier=mac`), a resolved drop-in (`MulticastDNS=yes`, `LLMNR=no`), the `/etc/resolv.conf` stub link, journal size limits, and `systemd-networkd-wait-online --any --timeout=30` | [9.2](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/network.html); systemd 261.2 `network/89-ethernet.network.example`; [systemd.network](https://www.freedesktop.org/software/systemd/man/latest/systemd.network.html), [resolved.conf](https://www.freedesktop.org/software/systemd/man/latest/resolved.conf.html), [journald.conf](https://www.freedesktop.org/software/systemd/man/latest/journald.conf.html), [systemd-networkd-wait-online](https://www.freedesktop.org/software/systemd/man/latest/systemd-networkd-wait-online.service.html) |
| `03-access.sh` | `/usr/lib/tup/remote/{policy,firewall,enroll}.py`, the four units, `/etc/tup/firewall.nft`, `/etc/issue`; enables the units and networkd, resolved and timesyncd with `systemctl --root=/`; asserts the generic final state | [agetty(8)](https://man7.org/linux/man-pages/man8/agetty.8.html) of util-linux 2.42.4, [systemctl(1)](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html) |

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
  `/var/lib/dbus/machine-id` to `/etc/machine-id`, and that check refuses a
  symbolic link there; this chapter does not touch it.
- The initramfs leaves the ISO-holding filesystem mounted at
  `/run/initramfs/isoscan`, and the kernel can mount FAT and exFAT.
- `/` and `/etc` on the live overlay are root-owned and not group-writable
  (sshd `StrictModes` and the enrollment preflight both require it).
- The console shows the state, an address through `\4`, and a fingerprint
  equal to the one `ssh` prints on the Mac.
- `ssh owner@tup.local` works; password login and root login are refused;
  `sudo -n true` works when sudo is installed.

## Not covered

- Exact scope on the boot that applies it: the unit already loaded by systemd
  does not wait for `network-online.target`. If the listen address is assigned
  later than sshd's five restart attempts (about 25 seconds), sshd stays down
  until the next boot. Enrollment installs an override unit that waits, which
  takes effect from the following boot of a persistent root. Prefer the
  default scope on a live boot.
- The hardware clock. TUP runs in UTC; once time is synchronized the kernel may
  write UTC to a clock that a dual-booted Windows expects in local time.
- Host key persistence on a live boot, key rotation, revocation, more than one
  owner, Wi-Fi, and any overlay or VPN.
