# LFS 13.1 source closure

`source-lock-13.1-build.json` authorizes a disposable native **build/test** from
all 94 selected inputs. It is **not release approval**: `release_eligible` is
false and Expat's unresolved CPU denial-of-service issue remains open as H55.
The dated Linux report records 83 authenticated inputs and 11 separately
accepted provenance exceptions. No observed download hash is presented as
publisher authentication, and no Sigstore verification is claimed.

| Verification or explicit exception | Inputs |
| --- | ---: |
| Published publisher HTTPS SHA256 | 38 |
| Published publisher HTTPS SHA512 | 1 |
| Live upstream OpenPGP signature | 9 |
| Live signed Gentoo snapshot and exact source Manifest | 34 |
| Signed Gentoo reference and exact decompressed Make tar comparison | 1 |
| Reviewed exact LFS patch provenance exception | 8 |
| Reviewed exact NetBSD HTTPS checksum exception | 2 |
| Reviewed exact LFS documentation exception | 1 |

`catalog-13.1.json` retains every original filename, URL and MD5 from the
13.1-systemd inventory. MD5 identifies a book input; it never authenticates
one. Named replacements in `selections-13.1.json` are Linux 6.18.60 LTS,
Python 3.14.10 and documentation, OpenSSL 4.0.3, Expat 2.10.0, util-linux
2.42.4, XZ 5.8.4, PCRE2 10.49, patch 2.8.1, Vim 9.2.1202, and revision 3 of
the glibc upstream fixes patch. Native recipe compatibility and package tests
remain separate requirements.

## Evidence and trust boundaries

`acquire.py` retrieves bounded HTTPS downloads into a private cache. Its
observed-byte receipts identify downloads; they do not authenticate them.
Publisher checksums come from retained release metadata, not the archive
being checked. Exact filename and release identities must match. The weaker
HTTPS classes explicitly make no signature claim, including checksum lists
whose embedded signatures were not verified.

`source_lock.py` checks real bytes and refuses missing or changed material,
wrong filenames, incomplete inventory, unapproved keys, weak signatures,
unreviewed exceptions and incomplete advisory coverage. GPG runs with an
isolated keyring, no automatic key retrieval, pinned key/signature material
and dated approval evidence. Signatures must use SHA256, SHA384 or SHA512;
expired-key status is refused. Actual GNU signatures and the Gentoo snapshot
passed this path; a real truncated snapshot failed signature verification.

The distributor trust root is Gentoo's ebuild repository primary fingerprint
`DCD05B71EAB94199527F44ACDB6B8C1F96D8BF6D`, approved through its
[official signing-key documentation](https://www.gentoo.org/downloads/signatures/).
The verifier authenticates `gentoo-20261103.tar.xz`, binds each retained
Manifest to its exact regular member in that signed snapshot, and compares
the upstream archive's filename, size and SHA512. The derived SHA256 pin
follows authentication. The full snapshot must remain available to reproduce
this proof; large archives stay outside Git. No snapshot member is extracted.

Make's upstream signing key has expired. Its gzip source is instead checked
against the signed distributor's `make-4.4.1.tar.lz`: maintained `lzip` decodes
the reference, Python's gzip decoder reads the selected source, and every
decompressed tar byte must agree. This uses the distinct
`distributor-openpgp-tar-equivalence` class. Both compressed identities,
common tar size/hash and decoder identity are retained. No source files or
upstream scripts are executed during this check.

Two provenance discrepancies remain visible. Automake's historical checksum
differs from the current artifact; its actual upstream signature and signed
Gentoo Manifest must both pass. The e2fsprogs SourceForge and kernel.org gzip
wrappers differ but contain identical complete tar bytes; selected bytes
match SourceForge's separately published SHA256. Neither mismatching
historical checksum is described as a passed check.

Exact reviewed exception policy hashes are enforced in the verifier:

- Eight LFS patches: official HTTPS plus reviewed unsigned Git commit/blob
  linkage, with application and package-test gates still mandatory.
- Tcl source and SQLite autoconf: exact filename, size and SHA512 from
  maintained NetBSD pkgsrc over HTTPS. These are distributor checksum
  exceptions, not publisher or distributor signatures.
- LFS-generated systemd manuals: exact immutable archive and complete
  1,256-member inventory, restricted to non-executable regular manual files
  and directories. Every verification regenerates the inventory. Native
  installation must confine output to `/usr/share/man`.

Exceptions have `accepted-exception` status and separate counts. They cannot
approve another name, digest, policy or executable package. Git text
conversion is disabled for retained evidence. Catalog identities and trust
anchors remain reviewed inputs, not self-authenticating declarations.

## Advisory coverage and release gate

The retained official POST response covers all 100 LFS 13.1 advisories through
2026-11-05. The verifier reparses actual records, checks their exact inventory
and package scope, and requires one disposition per record. Cross-reference
IDs in descriptions are not counted as extra advisories. Two upstream Expat
records cover the November 2 release and still-open CPU DoS.

There are 84 `not-in-base`, 15 `fixed-by-selection`, two
`fixed-by-native-patch` and one `deferred-release-gate` dispositions. Python
records bind the exact native patch/review for POP3 command validation and
allocation-based long-path resolution from immutable CPython 3.15.2 commit
`5e58eaad7c58df58dfa8ea549c87996e01dd1077`; Python 3.14.10 alone does not fix
those two issues. Native regression and package tests remain gates.

H55 is the only permitted release deferral. Expat 2.10.0 does not fix
CVE-2025-66382. Release requires host XML exposure review plus demonstrated
workload CPU/time containment, or qualification of a real upstream fix.
Unknown or unresolved deferrals cannot authorize export. Other packages need
separate review if added to boot, remote-access, isolation or workload layers.
Source closure does not establish kernel hardware support, secure remote
operation or successful system tests.

## Reproduce verification

Use Python 3.11 or newer, GPG and maintained `lzip`. Run from the repository
root with a private cache. Acquisition includes 94 selected inputs and two
separate verification dependencies; no source archive belongs in Git.

```sh
python3 tup/sources/acquire.py tup/sources/catalog-13.1.json --cache /private/source-cache --jobs 4
python3 tup/sources/source_lock.py tup/sources/catalog-13.1.json --cache /private/source-cache --evidence tup/sources/evidence/13.1 --gpg /usr/bin/gpg --lzip /usr/bin/lzip --report /private/source-verification.json --book-source tup/book-x86_64-13.1-systemd/BOOK-SOURCE --export /private/source-lock-13.1-build.json
python3 -m unittest discover -s tup/tests -p 'test_source*.py'
```

The CLI always re-verifies; an old report is not authorization. Do not consume
outputs after a failed command. Export preserves native source-lock v1 and
adds verification counts, per-input assurance, full dated advisory review,
`lock_purpose`, `release_eligible` and named release gates.
`transfer-manifest-13.1.json` inventories exact archives, verification
dependencies and evidence for a separately hashed Linux transfer. Book
provenance remains a separate review.

Primary references: [LFS inventory](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/wget-list-systemd),
[LFS advisories](https://www.linuxfromscratch.org/advisories/),
[GnuPG machine interface](https://www.gnupg.org/documentation/manuals/gnupg/Unattended-Usage-of-GPG.html),
[GNU release security](https://www.gnu.org/software/security/),
[Gentoo Manifest format](https://devmanual-cdn.gentoo.org/general-concepts/manifest/index.html),
[Lzip manual](https://www.nongnu.org/lzip/manual/lzip_manual.html),
[NetBSD pkgsrc distribution](https://www.netbsd.org/docs/pkgsrc/getting.html),
and [Expat open CPU issue](https://github.com/libexpat/libexpat/issues/1076).
