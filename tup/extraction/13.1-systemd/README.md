# Pinned LFS 13.1 systemd extraction

This checkpoint contains the original rendered book archive, its retrieval
record, and an explicit inventory review. It generates a separate book tree;
the historical x86_64 and ARM trees are unchanged.

The archive was retrieved from the [official LFS download directory](https://www.linuxfromscratch.org/lfs/downloads/13.1-systemd/LFS-BOOK-13.1.tar.xz).
Its SHA256 is
`090b2b127ac35634269d610e2649dab031fd8a5aa9acfaf10a3c971deda5ed89`
and its size is 259932 bytes. `snapshot.json` records the final URL and UTC
retrieval time. This is an **observed integrity pin**: no independently verified
publisher checksum or signature for this archive has been established. It does
not authenticate package downloads. The archive retains the book's original
license and legal notice pages.

From the repository root, verify the committed extraction entirely offline:

```sh
python3 tup/extract_book.py \
  --arch x86_64 --version 13.1 --init systemd --profile lfs-13.1-systemd \
  --snapshot tup/extraction/13.1-systemd/LFS-BOOK-13.1.tar.xz \
  --snapshot-metadata tup/extraction/13.1-systemd/snapshot.json \
  --audit-profile tup/extraction/13.1-systemd/audit-profile.json \
  --output tup/book-x86_64-13.1-systemd --check
python3 -m unittest tup.tests.test_extract_book -v
```

To reproduce into a new directory, omit `--check` and supply a nonexistent
`--output` directory. Existing different output and historical book destinations
are refused. The extractor hashes its own source, so changing it requires a new
extraction and review of the resulting identity. No book commands run during
extraction or these tests.

The pinned inventory contains 143 pages, 640 command blocks, and 94 entries from
`wget-list-systemd`. Master and chapter tables of contents must agree in exact
order. `audit-profile.json` binds page HTML, command text, suite classifications,
and every unresolved policy requirement to the raw archive. `EXTRACTION.json`
records the generated page hashes and classifications; `BOOK-SOURCE` binds the
snapshot, audit profile, source list, and extractor identities.

Every command-bearing page currently requires a named native override and exits
with status 97 before its preserved body. This checkpoint reviews the inventory
and identifies choices; it does not approve executing all commands. Architecture
alternatives, optional documentation, existing-system upgrades, interactive
configuration, cleanup, and physical installation commands remain visible for
explicit selection in the native profile. Native advisory replacements also
belong in named overrides, leaving the original book unchanged. No complete LFS
build or headless boot has been demonstrated by this checkpoint.

Each command is delimited by `# TUP_BLOCK_BEGIN=NNN` and
`# TUP_BLOCK_END=NNN`. Its SHA256 covers the UTF-8 command text, with outer source
`pre` newlines removed and all other whitespace preserved. The renderer adds
exactly one LF before the end marker; a block consumer must remove exactly that
separator LF before hashing. Suite policy wrappers remain outside these markers.
Combined build/test commands are classified separately so skipping a suite cannot
silently skip a package build. Unselected bodies are inside an unreachable quoted
heredoc so literal book placeholders still pass shell syntax checks.

The implementation builds on the existing extractor. The [jhalfs extraction
stylesheet](https://raw.githubusercontent.com/lfs-book/jhalfs/master/LFS/lfs.xsl)
provides prior art for explicit book-command policy; this path retains the
repository's rendered-HTML approach and requires an exact offline snapshot and
reviewed inventory. The [systemd page](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/systemd.html)
is a concrete regression case for non-`make` suites (`unshare -m ninja test`).
