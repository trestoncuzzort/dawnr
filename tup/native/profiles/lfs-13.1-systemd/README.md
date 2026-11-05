# Native 13.1-systemd core profile checkpoint

This directory is an incomplete profile. **No `AUDIT.json` is supplied yet,
and the native CLI still rejects a 13.1 build.** The historical 12.4 guard
remains active. Helper fixtures are not evidence that the new book builds.

The implemented review contract compiles an explicit, versioned block audit
into named overrides for every chapter 5–8 page. It binds the exact extracted
book metadata, complete chapter orders, original page bytes and every raw
command block. The generated book stays unchanged. The 13.1 staging helper
takes no executable override from the shared historical `tup/overrides` tree.

An audit must have schema `tup-native-block-audit-v1`, profile
`lfs-13.1-systemd`, the raw `BOOK-SOURCE` SHA256, exact `orders` for chapters
5–8, and one `pages` entry for every ordered page. Each page records its
`page_sha256`, optional replacement `archive`, and ordered `blocks`. Each block
records `id`, original `sha256`, `classification`, `action`, and a review
`reason`; replacement actions additionally contain explicit replacement code.
Missing/changed blocks or extra/missing pages refuse. Block digests match
`EXTRACTION.json`: remove exactly the one formatter newline before the end
delimiter, retaining every other command byte and trailing space.

The allowed actions are `run`, `run-suite`, `run-build-test`, `skip-suite`,
`omit`, `replace`, `replace-suite` and `delegate`. A test block requires an
explicit suite disposition. A combined build/test block cannot be skipped.
Started, passed, failed, skipped, changed and omitted actions remain distinct
in receipts. A nonzero required suite cannot emit a pass event. Host-side
crossings are delegated and refuse direct page execution.

The required suite policy is glibc, GCC, binutils, GMP and MPFR. The latter two
are explicitly critical in the maintained book. Historical record-only GCC
judgments and old-version failure allowlists are not inherited. Current-version
suite interpretation still needs its own review and measured evidence.

The source-lock interface accepts an explicit replacement archive on the
selected override while retaining the original book recipe hash. Production
13.1 source checks require the source lane's completed verification report,
verified per-source authentication evidence and reviewed advisory dispositions.
A candidate download or an unresolved advisory cannot satisfy those fields.
The expected source-lock digest must still come from independently reviewed
verification; the field values alone are not a cryptographic trust root.

Remaining work before activation:

- Complete and review the full block audit against the new extraction,
  including alternatives, examples, interactive commands and all test forms.
- Wire an explicit CLI profile selection, versioned host policy, bounded Ninja
  and Perl test parallelism, build-context variables and complete chapter-7
  crossing. Preserve root's full post-stage input validation.
- Audit the chosen Linux 6.18.60 headers, Python 3.14.10 and other advisory
  replacements against their actual source and patch contexts. Candidate
  archives currently have no production approval from this lane.
- Validate the source catalog's complete transitive inputs and final exported
  lock; retain unresolved source/advisory blockers.
- Run Linux driver/runner integration, all required suites and a clean core
  build, then continue with native boot, installer, networking and later goals.

Sources reviewed for this checkpoint:
[13.1 host requirements](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter02/hostreqs.html),
[chapter 7](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/chapter07.html),
[systemd tests](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/systemd.html),
and [Ninja parallelism](https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/ninja.html).
