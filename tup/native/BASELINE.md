# Maintained native baseline

Working decision, 2026-11-04: use **LFS 13.1-systemd with dated advisory
overrides** for the production native profile. Preserve the existing 12.4
SysV extraction and receipts as historical inputs. The current native builder
deliberately accepts only its audited 12.4 chapter crossing; it must refuse
the new book until the migration below is implemented and tested. Its current
fixture success is not approval to deploy either book unchanged.

The [LFS download page](https://www.linuxfromscratch.org/lfs/download.html)
states that the prior System V edition is no longer maintained. Keeping it
would make TUP responsible for its own backports and integration maintenance.
The maintained book reduces that work. TUP retains its source-built base,
named overrides, receipts and resource measurements. The selected headless
services and their measured cost must justify the configuration; no idle-RAM
claim has been measured yet.

These are required subitems of H54, with source authentication remaining H03:

1. Extend extraction to an explicit release/init/profile identity and a pinned
   book snapshot. `extract_book.py` currently chooses by architecture and
   hardcodes `wget-list-sysv`. Never overwrite the historical generated book
   or hand-edit extracted pages to make a migration appear complete.
2. Audit the exact chapter order by page name. The inspected 13.1 table of
   contents has 15 chapter-7 pages versus 13 in 12.4, and 10 chapter-9 pages
   versus 9. Chapter 8 still has 85 pages but different packages. A page-count
   check alone cannot establish completeness. The old numeric chapter-7 range
   would omit required work; unsupported order must refuse.
3. Revalidate every retained override. New packages include systemd, D-Bus,
   SQLite, PCRE2 and mpdecimal. The former `ch09/usage` override no longer
   matches a page. Networking, clocks, consoles, locales and supervision need
   an explicit native headless profile. Preserve generated alternative and
   interactive commands; select their intended behavior in named overrides.
4. Extend test classification beyond `make check/test`. The inspected systemd
   recipe invokes `unshare -m ninja test`, which bypasses the current guard.
   Revalidate package-version-specific glibc/GCC/binutils test judgments;
   report each required, skipped and failed suite honestly.
5. Review the current advisory application before fixing package versions.
   An untouched 13.1 release already has later advisories involving glibc,
   OpenSSL, Python, Expat, util-linux and XZ. Record advisory identifiers,
   affected versions, disposition and exact replacement/patch digests. The
   release number alone is not a security gate.
6. Provision unique machine identities and define persistent user jobs,
   session lifetime, journal/core-dump limits and temporary-directory behavior.
   Test those choices against owner reconnect and disposable-instance cleanup.
7. Bind all source inputs. The inspected systemd download list has 94 archive
   and patch entries. Use verified publisher signatures or published strong
   checksums with their trust class recorded. A SHA256 computed after download
   is an integrity observation, not source authentication. Keep unresolved
   source records blocked; do not automatically replace a mismatched pin.
8. Update the native host-requirement and chapter-crossing policies, then run a
   clean build. Re-run native boot, networking, service failure, update and
   rollback checks on that exact profile. EFI/install/GPU work remains separate.

For source verification, GNU artifacts can use approved signing fingerprints;
kernel signatures authenticate the uncompressed tar; Python's current
releases provide Sigstore evidence. Published HTTPS checksums are a distinct,
weaker trust class. Preserve the original verification material alongside the
lock, including source URLs and the evidence digest. Do not describe a freeform
`provenance` string or an observed lock hash as cryptographic verification.

Sources: [13.1 systemd build](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/systemd.html),
[13.1 service configuration](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/systemd-custom.html),
[current advisories](https://www.linuxfromscratch.org/advisories/),
[source acquisition](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter03/introduction.html),
[GNU verification](https://www.gnu.org/software/security/),
[kernel verification](https://www.kernel.org/signature.html),
[Python Sigstore](https://www.python.org/downloads/metadata/sigstore/).
