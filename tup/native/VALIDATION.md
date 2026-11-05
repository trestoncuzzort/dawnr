# Native entrypoint fixture evidence

2026-11-04: the prediction in `README.md` was checked with CPython 3.13.17 on
Windows x86_64. After review guards were added, the unittest suite ran
**17 tests, 0 failures, 0 skips**, in 0.390 seconds. Git for Windows Bash accepted both native shell files with
`bash -n`. No LFS page, mount, format, boot or network operation ran.

The fixtures accepted an unchanged pinned cache and checked refusals for
archive/lock/book tampering, wrong architecture, unsafe/duplicate source names,
insecure source URLs, symlink archives, overlapping workspace paths, CRLF shell
inputs, changed staged inputs, failed children, stale stage identities, changed
logs, failed driver-validation commands and failed receipt persistence both
before and after child execution. Additional cases refuse an unlisted staged
patch, changed source manifest, non-x86 book metadata, unsupported release and
changed chapter-7 order even when eight numeric05-12 pages still match. The
native root-locking override is selected from an explicit book/profile snapshot.

Commands:

```bash
python -m unittest discover -s tup/tests -p 'test_native_build.py' -v
bash -n tup/native/run-stage.sh
bash -n tup/native/profiles/x86_64/overrides/x86_64/ch08/shadow.sh
```

The Linux host preflight, actual `TUP_VALIDATE_ONLY` driver integration, mount
and PID namespace behavior, source/toolchain provenance closure, LFS chapter
builds and measured memory/resource bounds are **unrun**. The source lock is a
required external trust input and no production lock is supplied here. The
explicit book selector does not resolve the maintained-book/init-system choice
or approve historical LFS 12.4 for production. H01, H03–H06, H23 and H54 remain
open until their full integration/runtime gates have evidence.

Integration review on the same date reproduced one additional defect: a child
could change a transitive pinned patch, exit zero, and have the final chapter
marked complete. Full input/source postconditions now run before the stage
completion commit and again when validating a completed stage. A failed check
retains the running intent and prevents replay. The native suite now has
**19 passing fixtures**, including mutation by a successful child and refusal
without replay on a completed stage. The added integration checks also require
Bash >= 4.4 and GNU coreutils >= 8.24, inventory `sync`, and allow bounded
15-minute full-chapter validation rather than the 60-second tool-probe limit.
Actual Linux durability and timing still require Linux runs.

## Guarded 13.1 helper checkpoint

2026-11-05: the combined native fixture suite ran **31 tests, 0 failures,
0 skips** in 1.015 seconds with CPython 3.13.17 and Git for Windows Bash. The new
cases exercise delimiter-bound raw block selection, explicit Ninja test skips,
nonzero suite failure receipts, refusal to skip mixed build/test blocks,
root-lock replacement with a harmless command stub, wrong build-context
refusal, changed/incomplete block plans, ambiguous delimiters, archive
selection parity and unresolved source/advisory export refusal. The
formatter-newline regression preserves all other command bytes. An independent
read of the new extraction found exact digest agreement for **640 blocks
across 143 pages**, using `EXTRACTION.json` as the expected digest inventory.

Five additional driver protocol cases passed for replacement archives and
metadata ambiguity. Those Windows driver tests use the documented sync shim;
they do not establish Linux filesystem durability.

At that helper checkpoint the 13.1 CLI remained disabled and no reviewed
`AUDIT.json` existed. The next checkpoint below supersedes that activation state.
No new LFS page, mount or real package command ran in these fixtures. The
remaining activation and source/patch review work is named in the profile
checkpoint; none of H03/H54 or the native build/boot gates is closed by this
helper implementation.

## Reviewed native13 core checkpoint

2026-11-05: the explicit `lfs-13.1-systemd` CLI now renders the complete
124-page/580-block ch05-ch08 audit, with no historical shared override fallback.
The source lock must cover its exact 94 inputs, source assurance policy and
complete advisory review, including the Python backport bindings and H55
build-only gate. The `validate` action refuses incomplete stages without
executing a package and exports core-only evidence after fresh full validation.

The final portable native run completed **54 tests, 0 failures, 3 explicit
Linux-only skips**, in 5.026 seconds using CPython 3.13.17 and Git Bash. These
fixtures cover block coverage, exact source and
exception linkage, bounded clean runner environment, root/path protection,
retained suite evidence and test result formats, Python XML failures/skips,
manual archive confinement, changed backport digests and incomplete-stage
refusal. Three ownership/runner cases require Linux and are explicitly skipped
on Windows. All 124 rendered overrides pass Bash syntax checks. The integrated
Linux fixture run and first actual LFS build remain separate handoff gates.

Independent Linux regular-file checks are retained in the profile:

- `PATCH-APPLICATION.json`: all eight selected LFS patches apply with zero
  fuzz, exit 0, using GNU patch 2.7.6. The report binds the tool and patch inputs.
- `PYTHON-BACKPORT-REGRESSIONS.json`: both original vulnerable twins are
  rejected and both backported regressions pass with GCC 13.3.0. Exact upstream
  source/function changes, patch and tool identities are bound. The compiled
  harness checks long-path allocation, short destination, all relevant failure
  branches and freeing the returned buffer; the POP3 method rejects all 33
  prohibited control bytes without sending a command.

These isolated checks ran no package build/install commands. Real temporary
and final Python tests, complete compiler/math/package suites, mount namespace
behavior, native build resource measurements, boot, networking and remote
access still require their actual runtime evidence. SQLite local regressions
do not claim the full upstream suite absent from its selected archive. H55 and
the full native/remote-release goal remain open.
