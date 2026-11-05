# Reviewed LFS 13.1-systemd core profile

`AUDIT.json` binds the exact extracted book snapshot, all 124 selected pages,
580 raw command blocks, chapter order, per-block classifications/actions and
94 selected source names. The generated book is unchanged and remains guarded.
`build.py` renders named architecture-specific overrides from this allowlist;
changed/missing blocks or orders refuse. There is no fallback to a historical
shared override. The CLI profile is `lfs-13.1-systemd`; guarded recipe runtime
identity is `native-x86_64-lfs-13.1-systemd-core`.

## Decisions

- Use the book's fresh x86_64 build sequence and exact chapter 7 crossing. Root
  owns mount/ownership transitions; chroot executes pages 5-15. Optional backup
  and manual shell/host-unmount commands are omitted.
- Run the current glibc, binutils, GCC, GMP, MPFR, Tcl, Expect, coreutils,
  final Python, tar and kbd suites with at most four
  jobs. Preserve their console, .log/.sum/.out/.trs/.test-result files before
  package cleanup. Require zero command status, positive machine-readable
  results, no FAIL/XPASS/UNRESOLVED/ERROR verdict, and the expected GCC/binutils
  component summaries. Coreutils root and unprivileged phases retain separate
  records; stale root Automake verdicts are removed before the latter phase.
  Tcl/Expect use their Tcl summaries, tar/kbd Autotest summaries, and Python
  JUnit results. Every other optional suite is recorded as skipped.
- Combined build/test steps in Bzip2, Ninja and Python PGO still execute. Their
  receipts say build-test-complete, not that a separate full suite passed.
  Python PGO process count and Ninja's NINJAJOBS hook prevent implicit host-wide
  parallelism. Perl/Automake/Ninja/systemd/Expect test command variants are
  explicitly classified even when the extraction labels are conservative.
  Bzip2's embedded compression/decompression comparisons also retain required
  evidence. SQLite runs its shipped `.selftest` plus bounded transaction,
  constraint, JSON, FTS and integrity cases. That receipt explicitly says
  local built-binary regressions: this autoconf archive has no full upstream
  core testfixture suite. Kbd runs upstream tests and compiles all 18 patched
  maps using `--bkeymap`; it never loads a keymap into the kernel.
- Omit 32-bit examples, live glibc upgrade procedures, interactive commands,
  obsolete compatibility libraries, optional documentation and stripping.
  Keep the minimum test locales, UTC and debug symbols for first qualification.
- Build GRUB for x86_64 UEFI only. This installs files into the target root and
  never invokes grub-install or writes firmware/device state. Kernel, image,
  bootloader embedding and installation remain separate gates.
- Lock the root password and assert locked status; there is no shared password.
  Keep only localhost in /etc/hosts and an empty machine-id for later unique
  identity generation. Offline systemd presets start no services. Owner
  enrollment, remote credentials and supervision policy belong to later work.
- The Bash Expect heredoc and privileged util-linux test runner are explicitly
  test blocks. The latter is a post-boot procedure and is never run by this
  builder. Optional suites and post-boot gates remain untested, not passed.

The strict required-suite policy deliberately has **no known-failure allowlist**.
The book documents some glibc/GCC/binutils failures in chroot or on particular
hardware. A real run encountering one stops with all evidence retained. Any
current-version exception must be reviewed against that run and encoded with
positive coverage checks; a historical record-only success is not accepted.
Do not delete an intent and replay a partly installed page.

## Selected sources and patch review

The original release identities remain in the extracted book. Named overrides
select Linux headers 6.18.60, Python 3.14.10, OpenSSL 4.0.3, Expat 2.10.0,
util-linux 2.42.4, XZ 5.8.4, patch 2.8.1, PCRE2 10.49, Vim 9.2.1202 and glibc
2.44 upstream_fixes-3. Versioned document paths follow the selected packages.
The exact 94-input set includes auxiliary tarballs and patches, even when
optional documentation is not installed. Every input still needs source-lock
authentication and a reviewed advisory disposition; this file is not that proof.

The carried Python OpenSSL patch does not apply unchanged to Python 3.14.10:
its third commit expects the old end of test_msg_callback. The newer Python
adds descriptor security tests at that location. `adapt-python-openssl.py`
requires the exact original patch digest, changes only that hunk's context,
preserves the new security tests and inserts the original exception test after
them. All C hunks remain unchanged. GNU patch 2.7.6 applied the adapted patch
with `--batch --forward --fuzz=0` to isolated copies of the relevant candidate
archive files: exit 0; the unadapted patch exited 1. This is an applicability
check, not a compiled Python/OpenSSL runtime qualification or authentication.
`PATCH-APPLICATION.json` records the independent Linux check of all eight LFS
patches: eight zero exits and no fuzz, with actual patch executable identity.
Coreutils and kbd also need context-only adaptations; added/deleted patch lines
remain identical. Glibc's case-sensitive ADVISORIES/advisories tree requires a
Linux filesystem, as confirmed by the failed Windows copy and passing Linux check.

Observed compatibility inputs: Python archive SHA256
`de414a57119abef52784d8993e341d53aed635fc2b05c2607d9f98a2c5b72032`,
original patch `707a0c457192ac2f3b5b8a51481bc5ebd12db22d57c1dbe0256138ee6e070792`,
adapted patch `c8f0f5f31c71b28ad2d6ce04f895c1611dfc0e7744aa538134b71dfa71b4eef6`.
The independent source-lock verifier must authenticate the original inputs;
these observed digests constrain compatibility and do not create trust.

Python 3.14.10 does not contain two selected advisory fixes. The separate
`python-3.14.10-security-backports.patch` copies the precise POP3 control-character
check and allocated-realpath change from upstream v3.15.2 commit
`5e58eaad7c58df58dfa8ea549c87996e01dd1077`. The review binds original/selected
file bytes and upstream URLs. `PYTHON-BACKPORT-REGRESSIONS.json` records that
both vulnerable twins failed and both corrected regressions passed on Linux;
the C harness executes the actual selected function with controlled allocation
and error boundaries. This is not a complete Python runtime qualification.
The build applies the patches before both temporary and final Python configure,
repeats focused tests with the newly built temporary interpreter, and runs the
available final Python suite with bounded jobs and retained XML. The source
lock must bind both native patch and review digests for advisories 088/089.

Eight carried LFS patches are exact reviewed unsigned Git/TLS provenance
exceptions. Tcl and SQLite have exact NetBSD HTTPS corroboration exceptions;
the systemd manual archive has a separate documentation-only exception.
`REMAINING-SOURCE-PROVENANCE.json` retains the approved three-source policy.
`install-systemd-man.py` checks the 1256-member manual-only archive and confines
installation to real `/usr/share/man` paths with non-executable file modes.
None of these exceptions is described as publisher signature verification.

Expat 2.10.0 still has the acknowledged CPU denial-of-service issue
CVE-2025-66382. The exact H55 build-only deferral is carried into every core
completion export; it does not establish production release eligibility.

The maintained source/advisory lane owns current verification and unresolved
release gates. A successful core build cannot by itself establish exposure
containment, boot/remote operation or production release readiness.

## Sources

The command source is the pinned [LFS 13.1-systemd book](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/).
Selections follow the [LFS advisories](https://www.linuxfromscratch.org/advisories/),
[current glibc patch instructions](https://www.linuxfromscratch.org/lfs/view/development/chapter08/glibc.html),
[Python 3.14.10](https://www.python.org/downloads/release/python-31410/) and
[kernel releases](https://www.kernel.org/releases.json). Required test policy
is grounded in the corresponding chapter-8 package pages and the reviewed
GMP/MPFR Automake and glibc/DejaGNU result formats. The parent native validation
record distinguishes fixtures and patch applicability from unrun native builds.
