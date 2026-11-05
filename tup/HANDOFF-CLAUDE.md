# TUP handoff to Claude — paused 2026-11-05

The owner explicitly requested **pause and write a handoff to Claude**. Work is
paused, the automatic goal was cleared, and no next build has been started.
This is an unfinished project, not a completion report. Resume implementation
only when the owner asks Claude to continue.

The latest integrated code is dawnr main
`d35a0ff349e432f02cfcc3be50f2df3d62d429fe`, pushed to origin. This handoff and
its accompanying evidence are a subsequent documentation checkpoint.
Unfinished worker files are preserved separately, as described below.

## Intended result and authority

Read [HEADLESS-GOAL.md](HEADLESS-GOAL.md) in full, then
[HEADLESS-HURDLES.json](HEADLESS-HURDLES.json) (55 tracked hurdles) and
[HEADLESS-STATUS.md](HEADLESS-STATUS.md). The owner's latest request to pause
takes precedence over the earlier instruction to work continuously.

- Build **native x86_64 TUP from dawnr/tup's LFS foundation**, replacing Windows
  eventually. Use this repository, not the standalone tup repository. The
  owner's explicit choice overrides the older repository split-out instruction.
- Deliver a Ventoy-compatible TUP installer/rescue ISO. Installed TUP and its
  installer must run without Windows or QEMU. External x86_64 QEMU tests are
  authorized; they do not qualify physical hardware.
- Keep the desktop running headlessly, with protected owner access from a new
  MacBook and useful CPU/RAM/RTX 4080 workloads.
- Later add Qubes-inspired **separate-kernel** disposable TUP guests, with a
  package manager inside each guest. Disconnect preserves jobs; explicit finish
  discards guest packages/private writable state. Only selected exports persist.
- Owner access comes first. Do not publish services or admit other users as a
  side effect. Containers alone do not meet the separate-kernel requirement.
- Backups are already confirmed. **Before erasing any physical USB or disk,
  finish disposable qualification, present the exact target and partition plan,
  and obtain confirmation.** Two similar-capacity internal disks exist. Windows
  reporting one as RAW is not evidence that it is empty. No physical storage has
  been erased, formatted or installed by this workflow.
- The owner authorized ordinary pushes directly to dawnr/main and delegated
  work. Keep private enrollment, keys, addresses, disk identifiers and machine
  paths out of this public repository. Never force-push.

The owner was frustrated by the time spent before a first real boot. They
explicitly requested [fetch-before-fic](skills/fetch-before-fic/SKILL.md), which
is created, validated, committed and installed in the local skill directory.
Read it. Search the repository and maintained upstream implementation first,
reuse supported interfaces, and write the smallest necessary adaptation. Do
not spend the next session building another generic framework or repeating
unchanged fixture suites. Preserve useful existing evidence and working code.

## Immediate blocker: actual core build failed

The first native-profile core run used frozen source commit
`cbabbd393a6d6d1470329d6b64defeafaf0f0392`. Chapters 5 and 6 passed, including
both GCC passes. Chapter 7 passed through mpdecimal. At
**ch07-inner/12-Python.sh**, compilation completed, then the added security
regression command invoked bare `./python` and failed:

```text
./python: error while loading shared libraries: libpython3.14.so.1.0:
cannot open shared object file: No such file or directory
required suite result evidence is missing or reports failures
target may be partially modified; refusing automatic retry (intent retained).
```

The missing optional OpenSSL and other Python modules printed immediately
before this are expected at this temporary stage; they are not the observed
exit-127 cause. Do not weaken the required regression result checks.

The native worker confirmed the built CPython Makefile contains
`RUNSHARED=LD_LIBRARY_PATH=/sources/Python-3.14.10` and
`PYTHON_FOR_BUILD=./$(BUILDPYTHON) -E`. Upstream's own commands use
`$(RUNSHARED) $(PYTHON_FOR_BUILD)` successfully. The added bare invocation does
not. Proposed minimal fix, **not implemented or tested**: invoke the regression
through a small supplementary Makefile target using those upstream variables,
and update the exact audited suite replacement. Reproduce using an isolated
copy with the target loader/libraries; host Python libraries are not equivalent.
Check the corresponding final Python invocation too.

Preserve the failed workspace, frozen inputs, page intent and original logs.
Do not delete its failure marker, edit the frozen recipe, or relabel a rerun as
the original build. A fresh workspace with corrected, committed inputs is the
straightforward next full-build path after the fix is demonstrated. No second
core run has been prepared or launched.

The failed run lasted 1,929.15 seconds. Its enforced limits were four compile
jobs, 4 GiB memory, 2 GiB swap and four CPUs. Peak charged memory reached 4 GiB;
maximum observed swap was 1,366,396,928 bytes. There were **zero OOM kills** and
zero remaining tasks in the collector's final observation. This establishes
resource behavior only for the failed partial build, not a full build or stress
qualification. See [the failure receipt](receipts/native-dev-20261105/core-001-failure.json).

The service is failed/stopped, with exit status 2, and no core-completion receipt
exists. At pause, all worker lanes reported stopped; the disposable QEMU had
terminated and the loop-device list was empty. The Linux environment itself
remains available. Private paths and exact commands are in the local handoff.

## What has actually passed

| Area | Measured result | Important boundary |
| --- | --- | --- |
| Main integration | **290 Linux tests, zero skips** at d35a0ff3; [receipt](receipts/native-dev-20261105/verification-d35a0ff3.json), [raw log](receipts/native-dev-20261105/integration-d35a0ff3-linux.txt) | Fixtures do not establish an OS boot or remote login |
| Core sources | 94 accepted: 83 authenticated plus 11 exact, reviewed provenance exceptions; 102 advisory dispositions | Build-only eligibility; open Expat gate H55 |
| Native recipe | Maintained LFS 13.1-systemd profile; 124 audited pages / 580 blocks; generated historical books retained | Actual core failed during temporary Python; chapter 8 has not run |
| Patches | Eight LFS patches applied with zero fuzz; two Python security regressions reject vulnerable twins and accept patched cases | Independent patch tests do not excuse the failed target invocation |
| Host boot tools | Authenticated dracut 112, GRUB 2.14 EFI and SquashFS 4.7.5 built; actual metadata roundtrip and EFI packaging passed | These are builder tools, not a booted TUP kernel/root |
| Direct UEFI smoke | External QEMU/OVMF ran a minimal host GRUB marker and exited successfully | Explicit TCG, 1 vCPU / 256 MiB; no TUP userspace or SSH |
| Disposable installer | systemd-repart 255 populated a regular-file GPT/ESP/ext4 image; payload and metadata checks passed; 24 Linux tests | Not target systemd 261, full TUP installation, installed boot or physical installer |
| Remote sources | OpenSSH 10.6p1, nftables 1.1.7, libnftnl 1.3.2 and libmnl 1.0.5 authenticated | Target builds and remote login remain unrun |
| Remote policy | Actual host OpenSSH effective-config check; isolated IPv4/IPv6 firewall admission/denial, reload, rollback and existing-flow revocation | No real owner enrollment, host firewall activation or VPN |
| Firewall libraries | Host libnftnl upstream suite 32/32 passed | Host build is not a target binary |
| Hardware inputs | Actual Linux 6.18.60 Kconfig resolution passes boot/wired/nftables checks; authenticated selected firmware staged separately | No kernel build, NIC probe, firmware load or GPU workload |

The core source-lock SHA256 is
`8c46c28a74f760ddf62df17f34327ac24dde7b465ab7c1bf3b9dbc7551522a05`.
Exact provenance exceptions and advisory decisions live under [sources/](sources/).
Make's old expired publisher key was refused; signed distributor evidence and
whole decompressed-tar equivalence were used instead. Do not discard the
retained conflicts or turn exceptions into publisher-authentication claims.

**H55 remains open:** Expat CVE-2025-66382 has no public triggering input or
qualified fix in this workflow. The source lock and artifacts must retain
`release_eligible=false` until exposure review and measured containment meet the
goal. Do not describe a parser load test as an exploit-specific fix.

## Preserved unfinished work

These files are **not on main** and must be reviewed before integration. The
private handoff includes their exact paths and a snapshot of the drafts. Do not
cherry-pick whole worker histories: prior owned commits were already integrated
under different hashes.

| Worktree branch | State at pause | Next action on resumption |
| --- | --- | --- |
| `work/tup-native-hardware` at ab6d8d07 | Hardware commit integrated as d35a0ff3; no tracked modifications. Python diagnosis above. Boot pages researched but not created. | Fix actual Python failure first |
| `work/tup-remote-ops` at 546a140b | Untracked `remote/build_target.py`, `remote/run-target.sh`, `remote/target-common.sh`, four `remote/pages/` scripts plus ORDER, `tests/test_remote_target.py` | Review and test actual target-runner assumptions after a complete core |
| `work/tup-runtime-smoke` at 0e6f40d4 | Untracked `boot/tests-runtime/`; disposable Ventoy preparation and smoke evidence retained | Inspect timed-out Ventoy smoke; do not report a full pass |

The remote draft reuses the existing core validator/completion check, exports a
separate root with rsync, excludes original build/runtime directories, and uses
the existing driver with a fresh `/sources/log`. It retains layer evidence
outside the final export. Original core evidence must remain untouched. It
uses private mount/network/PID/UTS namespaces and a removable UID/GID 51
`sshtest` account via Shadow `su`: LFS disables `runuser` and `setpriv`. Root
remains locked. A small Windows fixture run preceded its last namespace edit;
the target runner itself and current shell scripts have **not run**.

The agreed optional boot phase in that runner is **not implemented**. Reuse the
same export/ledger contract rather than adding another generic mount runner or
new driver-log API. Needed ordinary pages: libaio 0.3.113, device-mapper-only
LVM2 2.03.42, Linux 6.18.60 and selected linux-firmware 20261019. Authenticated
source records already exist. LVM2 supports `make device-mapper` and
`make install_device-mapper`. Its full device-manipulating suite needs an
appropriate isolated test environment; do not run it blindly on the builder.

Boot packaging still passes `--no-early-microcode`. A proposed change, **not
implemented**, is `--early-microcode` with an explicit firmware directory in the
export, then use maintained `lsinitrd --unpackearly` in a fresh staging directory
and compare `kernel/x86/microcode/AuthenticAMD.bin` with the selected family-19h
input. Dracut 112 in non-host-only mode concatenates AMD files from its firmware
directories. Avoid accidentally collecting builder firmware; no custom CPIO
parser is needed.

## Actual failures and implementation traps to preserve

- **Ventoy smoke:** authenticated Ventoy 1.1.18 was installed onto a disposable
  1 GiB regular-file image using upstream tooling. The copied ISO was re-read
  byte-for-byte. USB-emulated UEFI boot reached `TUP-HOST-EFI-SMOKE`, but GRUB's
  `halt` did not terminate QEMU within 60 seconds. The stored verdict is
  **FAILED**, and the wrapper terminated QEMU. This is partial handoff evidence,
  not a TUP boot, shutdown or installer pass.
- Ventoy's inspected installer marks its second GPT partition Microsoft basic
  data even though its layout prose describes an ESP. An initial postcheck
  rejected that discrepancy; the retained second test checks the actual vendor
  layout, FAT and EFI fallback files.
- Ventoy invokes `partprobe` without a device. The disposable wrapper confines
  this to the verified image-backed loop and checks upstream mount-prefix
  handling. Do not let a broad rescan/unmount touch other devices.
- **systemd-repart:** `--empty=create` overrides dry-run in the inspected
  versions, and `--split=yes` can write during a dry-run. Current image tooling
  uses a precreated zero regular file, `--empty=require --split=no`, an exact
  target identity and a whole-image no-write check. The first failed probe is
  retained. Physical devices are deliberately refused by this implementation.
- Raw POSIX ACL bytes from debugfs differed in unused ID fields. The fixture
  now compares kernel-canonicalized ACL semantics, preserving named IDs and
  permissions. Keep the failed comparison in the evidence.
- On systemd 255, transient `MemoryOOMGroup=yes` was unsupported and refused
  before launch. Documented `OOMPolicy=kill` was used; `memory.oom.group=1` was
  checked. Do not repeat the unsupported property.
- A finite SSH restart limit can leave sshd stopped if its address arrives late.
  Multiple fixed ListenAddress values have another failure: one can bind while
  another is absent, leaving sshd alive but incompletely listening. Upstream
  systemd `FreeBind` sockets with OpenSSH inetd mode are a researched candidate,
  **not an implemented or tested fix**. Late-network recovery, owner privilege
  escalation and durable-job policy remain open.
- The built-in Realtek Ethernet path has a configuration/firmware floor. The
  active USB Wi-Fi maps to RTL8852CU, absent from selected Linux 6.18.60. Related
  8852BU or PCI 8852CE support is not this device's driver.
- `/dev/kvm` exists in the builder, but opening it returned ENODEV. External
  test results must identify **TCG**, not claim hardware acceleration.

## Order of work when the owner resumes

1. Read the private handoff and inspect preserved state. Fix and demonstrate
   the Python invocation using the upstream Makefile variables. Keep the
   required result evidence and audited input binding.
2. Commit the fix, run appropriate affected checks, freeze a new input tree and
   launch a fresh bounded core build. Preserve run 001. Do not run the old
   one-shot preparation helper unchanged: its paths already exist.
3. Validate the completed core with its **same frozen runner and flags**, then
   export a separate root. Build the minimal remote and boot layers with their
   existing interfaces, preserving original core receipts.
4. Build actual TUP kernel/initramfs/ISO; run direct UEFI boot and real SSH login.
   Then qualify that exact image through disposable Ventoy and a disposable
   installed disk, including failure and recovery cases.
5. Only then present the physical USB plan for approval and perform a live
   hardware trial. Actual NIC, GPU, thermals, IOMMU, recovery and independent
   installed boot need physical evidence. Do not count VM checks as those tests.
6. Finish private remote operations, GPU compute, separate-kernel disposable
   guests/package manager, rollback/restore and the declared soak plan. Keep all
   unresolved hurdles visible. Nothing close to these final gates has passed yet.

The user was given a rough conditional estimate of 6–12 more hours to a first
headless boot/login, followed by another 1–3 days for broader qualification.
That was not a measured deadline; the Python failure was reported immediately
after discovery. Re-estimate from the next actual complete build rather than
promising a fixed finish time.

No complete native TUP core, target kernel, bootable TUP ISO, installed TUP,
actual remote login, CUDA workload, guest isolation or hardware stress pass
exists at this pause. The next useful result is a corrected, completed core.
