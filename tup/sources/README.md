# LFS 13.1 source verification checkpoint

This is a candidate inventory, not an approved production lock. The dated
`verification-13.1.json` records verification of **22 of 94** selected source
archives and patches. All 22 use the explicitly weaker
`https-published-sha256` class. No publisher OpenPGP or Sigstore signature has
been verified in this checkpoint. `advisory_review` remains unresolved, so
production export is refused independently of source verification.

`catalog-13.1.json` preserves every filename, URL and MD5 from the original
13.1-systemd inventory, including the eight LFS patches. MD5 identifies the
book input only; it never authenticates a file. The selected replacements and
their reasons are in `selections-13.1.json`: Linux 6.18.60 LTS, Python 3.14.10
and matching documentation, OpenSSL 4.0.3, Expat 2.9.0, util-linux 2.42.4 and
XZ 5.8.4. These are source candidates; build-command compatibility and complete
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
tar bytes without extracting files. This path has status-parser fixtures but
has not yet been exercised against an approved live publisher signature.
Sigstore verification is not implemented and is never claimed.

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
  --report /private/source-verification.json
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

The report names all 72 unresolved inputs. The acquisition attempt cached 72
of 94 inputs; 22 GNU downloads timed out. Download success and authentication
counts are independent. Of the unresolved inputs, 50 are cached but have no
accepted publisher authentication evidence yet.

- Complete GNU and other publisher key/signature approval and actual GPG
  verification. Never infer trust solely from a key ID in a signature.
- Resolve the Python release-page digest selector; its current HTML format
  did not match, so Python 3.14.10 remains unverified. Its Sigstore materials
  also require a real verifier and approved identity/issuer policy if used.
- Find publisher evidence for older GitHub assets lacking API digest fields
  (bc, flex, lz4 and zstd), generated GitHub archives, documentation archives
  and remaining non-GNU packages.
- Establish an acceptable strong authentication path for all eight LFS
  patches. The book's MD5 list and locally computed SHA256 values do not
  satisfy this requirement.
- Capture the current LFS advisory application response and review every
  baseline-related advisory. In particular, independently resolve the Expat
  issues mentioned by sa-13.1-045, including CVE-2025-66382 and CVE-2026-66046;
  do not assume selecting 2.9.0 resolves them. Bind that dated review and its
  complete coverage to retained evidence before approving production export.
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
