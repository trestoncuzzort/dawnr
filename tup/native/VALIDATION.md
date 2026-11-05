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

The 13.1 CLI remains disabled and no reviewed production `AUDIT.json` exists.
No new LFS page, mount or real package command ran in these fixtures. The
remaining activation and source/patch review work is named in the profile
checkpoint; none of H03/H54 or the native build/boot gates is closed by this
helper implementation.
