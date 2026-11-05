# LFS 13.1 source verification checkpoint

This is a candidate inventory, not an approved production lock. The dated
`verification-13.1.json` records verification of **75 of 94** selected source
archives and patches: 8 upstream OpenPGP signatures, 34 published HTTPS SHA256
checks and 33 exact source matches through an authenticated Gentoo snapshot.
Sigstore verification is not claimed. `advisory_review` remains unresolved, so
production export is refused independently of source verification.

`catalog-13.1.json` preserves every filename, URL and MD5 from the original
13.1-systemd inventory, including the eight LFS patches. MD5 identifies the
book input only; it never authenticates a file. The selected replacements and
their reasons are in `selections-13.1.json`: Linux 6.18.60 LTS, Python 3.14.10
and matching documentation, OpenSSL 4.0.3, Expat 2.10.0, util-linux 2.42.4,
XZ 5.8.4, PCRE2 10.49, patch 2.8.1, Vim 9.2.1201 and revision 3 of the glibc
upstream fixes patch. These are source candidates; build-command compatibility and complete
security-advisory disposition are separate requirements.

## What the tools check

`acquire.py` downloads over HTTPS to a caller-selected private cache, with a
per-file size limit, bounded concurrency and an observed-byte receipt. It
never runs or unpacks upstream code. A download receipt is not authentication.

`collect_evidence.py` obtains publisher metadata without deriving an expected
hash from the downloaded archive. It retains exact metadata bytes and selects
one filename and release tag/version. GitHub release asset digests, PyPI
release metadata and kernel.org checksum lists are published HTTPS evidence.
A checksum inside a signed `.asc` file still receives the weaker HTTPS class
unless its signature is actually verified.

`source_lock.py` compares the cached archive bytes with the selected published
digest. It rejects missing or changed evidence, wrong or duplicate filename
matches, altered archives, missing baseline entries and unresolved inputs.
Its OpenPGP path invokes a supplied GPG executable with an isolated keyring,
no automatic key retrieval, pinned key/signature material and an explicitly
approved primary fingerprint. It accepts SHA256/384/512 signatures, verifies
the machine-readable status and can check kernel signatures over decompressed
tar bytes without extracting files. This path has been exercised on actual
GNU releases and the Gentoo snapshot. A live negative control rejected a
truncated snapshot using the real snapshot signature and approved key.
Sigstore verification is not implemented and is never claimed.

The distinct `distributor-openpgp-manifest` class uses the official Gentoo
ebuild repository key, primary fingerprint
`DCD05B71EAB94199527F44ACDB6B8C1F96D8BF6D`, published in
[Gentoo's signing-key documentation](https://www.gentoo.org/downloads/signatures/).
The verifier authenticates the dated `gentoo-20261103.tar.xz` snapshot, checks
that each retained package Manifest is exactly the member in that signed
snapshot, then checks the upstream archive's exact filename, size and SHA512.
The SHA256 lock pin is derived only after that verification. The complete
snapshot stays in the private cache; its signature, key, approval page and
selected Manifests are retained here. No snapshot member is extracted to a
filesystem. GNU mirrors are reviewed delivery alternatives, while original
upstream URLs remain in the catalog.

Automake 1.18.1 has an explicit provenance conflict: its historical release
announcement's SHA256 differs from the current artifact. The actual release
signature verifies under the primary named by that announcement, and the
independently signed Gentoo Manifest agrees with the current bytes. Both
checks are required. The failed historical checksum remains recorded under
`integrity_review`; it is never presented as a passed checksum.

The catalog, publisher URLs, approved fingerprints and advisory dispositions
are reviewed trust inputs. Their stored hashes detect changes after review;
they do not make an unreviewed publisher or key trustworthy. Retained evidence
has Git text conversion disabled so checkout preserves its raw bytes.

## Reproduce the checkpoint

Use Python 3.11 or newer. Run from the repository root and supply your own
private cache path. No source archive belongs in this repository.

```sh
python3 tup/sources/acquire.py tup/sources/catalog-13.1.json \
  --cache /private/source-cache --jobs 4
python3 tup/sources/source_lock.py tup/sources/catalog-13.1.json \
  --cache /private/source-cache --evidence tup/sources/evidence/13.1 \
  --gpg /path/to/gpg --report /private/source-verification.json
python3 -m unittest discover -s tup/tests -p 'test_source*.py'
```

The verifier returns nonzero until every record verifies. `--export` also
requires `--book-source`, a complete source report and a dated advisory review
with no unresolved dispositions. The CLI always re-verifies source bytes;
it does not accept a previously generated report as authorization. Do not
consume an output file after a failed command. A successful export preserves
the native `tup-source-lock-v1` fields and adds:

- `source_verification`: schema, complete status, report hash, source count
  and check time.
- Per-source `authentication`: verified status, evidence hash, trust class
  and verifier details; `verification_material` identifies retained material.
- `advisory_review`: reviewed status, review date, material hash and explicit
  `fixed-by-selection`, `not-affected` or `not-in-base` dispositions.

## Remaining work

The report names all 19 unresolved inputs. All 94 currently selected inputs
are cached, as is the separate signed Gentoo verification snapshot. Download
success and authentication counts are independent.

- Complete the remaining 11 non-patch sources: attr, e2fsprogs, make,
  procps-ng, SQLite autoconf, systemd man pages, Tcl source and documentation,
  tzdata, Vim and zlib. Never infer trust solely from a key ID in a signature.
- All eight LFS patches match exact official Git blobs, including reviewed
  symlink resolution, at the commit in `lfs-patch-corroboration-13.1.json`.
  That commit is unsigned, and no strong publisher checksum was established.
  A narrowly named provenance exception still needs explicit review and
  application evidence; these records remain unresolved, not authenticated.
- Capture the current LFS advisory application response and review every
  baseline-related advisory. In particular, independently resolve the Expat
  issues mentioned by sa-13.1-045. Expat 2.10.0 adds four security fixes after
  the current LFS advisory snapshot, but CVE-2025-66382 remains open upstream.
  H55 must explicitly separate permission to build/test from release readiness;
  it cannot be described as fixed. Bind the dated review and its complete
  coverage to retained evidence before approving any lock export.
- Confirm the Python OpenSSL patch applies to 3.14.10, review the glibc patch,
  and complete native overrides. Book archive authentication is also separate:
  the extractor's observed archive hash is not publisher authentication.

Primary references: [LFS package inventory](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/wget-list-systemd),
[LFS advisories](https://www.linuxfromscratch.org/advisories/),
[GnuPG machine interface](https://www.gnupg.org/documentation/manuals/gnupg/Unattended-Usage-of-GPG.html),
[GNU release security](https://www.gnu.org/software/security/),
[kernel signature verification](https://www.kernel.org/signature.html),
[PyPI JSON API](https://docs.pypi.org/api/json/),
[Python Sigstore verification](https://www.python.org/downloads/metadata/sigstore/),
and [GitHub source archive limits](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives).
