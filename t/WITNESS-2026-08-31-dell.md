# t: Dell witness, 2026-08-31 (ubuntu-box, Ubuntu 24.04, x86_64)

WS-7's step zero, run after the machine wipe: every kernel reinstalled
no-sudo from pinned, hashed artifacts, then the full 11-task suite through
`run_all.py`. Result: **65 of 66 cells `verified / refuted`**, the measured
flip on every task for dafny, verus, spark, framac, lean, and 10 of 11 for
rocq. The one non-flip is a recorded finding, not noise:

    count_matches x rocq: real=TIMEOUT, twin=REFUTED
    (rocq is the one kernel with no deterministic budget; its adapter's
    180 s wall backstop fired on the real lowering, three runs of three.)

This run is also two discharges the v1 commit left pending:

- **The Verus remeasure.** All 11 Verus cells flip, the first honest
  measurement since the filename-artifact audit. And the audit's repair
  itself needed repairing: the "error[" stderr match missed rustc's bare
  `error: invalid character '.' in crate name` diagnostic, so a dotted-name
  twin STILL scored REFUTED (verified=0, errors=0, measured here today).
  verifiers/verus.py now awards REFUTED only on the solver's own nonzero
  errors count; the measured flip table for the patch: real abs.rs
  verified, dot-free twin refuted (errors=1), dotted twin malformed
  (errors=0).
- **The full-suite re-run.** AGREEMENT.md regenerated on this box with the
  Dell backend identities.

And one surprise in the good direction: the Rocq v1 lowering, recorded as
"unfinished by decision," lowers and flips 10 of 11 tasks as landed. The
parked finisher's remaining scope is one cell: the count_matches timeout.

The suite was then re-run through `run_par.py` (cell-parallel, built and
adversarially reviewed today): its AGREEMENT.md is byte-identical to the
serial table modulo timestamp: serial 27 min, parallel 9 min. Its live-run
guard also paid the house's pgrep-self-match lesson once more before being
fixed to basename-equality matching (first launch refused against its own
launcher shell; measured, recorded in the code comment).

## Toolchain fingerprints (sha256, first 16)

    e540b4826363afb8  ~/.local/dafny/dafny                     (dafny 4.11.0+fcb2042d)
    0b7a8b2c97a4c281  ~/.local/verus/verus-x86-linux/verus     (verus 0.2026.08.30.b432e82)
    544e6da2eedc24ce  ~/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin/gnatprove
    e8baaa71855a616d  ~/.elan/toolchains/leanprover--lean4---v4.33.1/bin/lean
    e87585e442267779  ~/.opam/default/bin/coqc                 (Rocq 9.2, via coq-core compat)
    3a7dedd3a363d088  ~/.opam/default/bin/rocqchk
    dbf5807f638d84e4  ~/.opam/default/bin/frama-c              (33.0 Arsenic)
    0a7ed0ccbc3a51d8  ~/.opam/default/bin/alt-ergo             (2.4.3-free, license-verified)
    60b38f8e33de178a  ~/.opam/default/bin/why3                 (1.8.2)

## Install provenance (every artifact hashed before use)

    a46a9ff7cdd720f7…  dafny-4.11.0-x64-ubuntu-22.04.zip
    067f5f72a457fe66…  verus-0.2026.08.30.b432e82-x86-linux.zip
    82528bef29857e23…  gnatprove-x86_64-linux-16.1.0-1.tar.gz (3-way match: measured,
                       release's own .sha256 asset, alire-index crate manifest)
    a620ff1641616222…  elan-init.sh (leanprover/elan @ 0e36a07b)
    edfca2630c373b44…  opam-2.5.2-x86_64-linux
    a45280ab4fbaac75…  rocq-9.2.0.tar.gz
    f2ee1cb0b9af3e7b…  stdlib-9.2.0.tar.gz

Two install findings, banked for the record: `rocq-stdlib` 9.2.0 is not
published on opam (tops out 9.1.0), so it is pinned here from the upstream
rocq-prover/stdlib V9.2.0 release tarball; and Rocq 9.2's `rocq-core` ships
no `coqc` at all: the binary the adapter invokes comes from the first-party
`coq-core.9.2.0` compatibility package. Build-time system deps (gmp headers,
autoconf, graphviz) came from a disposable conda env with zero runtime
linkage (verified via readelf: no RPATH into the env; deletable).

Verdict basis: the suite's own AGREEMENT.md hashes the lowered sources;
backend identities as listed there. Verus requires `~/.cargo/bin` on PATH
(rustup toolchain 1.97.1, pinned by the release's own demand).

---

# Evening addendum: the matrix goes to 7 kernels, 77/77

Same box, same day. Three fronts closed by a Fable agent fan-out, every
claim re-measured in the main session before landing:

**count_matches x rocq FIXED, root cause and not workaround.** The generated
prelude's `t_merge` saturation step lacked an occurs check: when one merge
term syntactically contained the other, Ltac could orient the rewrite so
each `replace` re-created its own trigger (`-1+1` chains growing without
bound; probed to 30 saturation steps, still growing). Only count_matches
exposed it: its spec_fun unfolding plus a `subst` on the loop guard puts
two same-function applications at lia-equal, syntactically distinct indices
into one goal. One shared structural edit (two occurs-check arms ahead of
the numeral guards, the containing term always the one replaced, strictly
shrinking, cannot re-fire). No task is name-keyed; the spec is untouched.
Real now verifies in ~0.62 s (was 3 x 180 s TIMEOUT); all 11 rocq rows
re-measured, no regressions (seq_max ~55 s and linear_search twin ~151 s
predate the change, re-timed on reconstructed before-sources to prove it).

**F* is the seventh kernel.** Official binary v2026.08.30 (hashed), bundled
Z3 4.13.3, `--z3seed 42 --z3rlimit --report_assumes error`, never composed
with `--cache_off`, fresh scratch dir per verify. The five-way taxonomy was
measured on this box before the adapter was written (19 refuted/timeout
split by message text, 335 vacuity, 168/72 malformed, 129 tool-error), and
the adapter classifies from those measurements, not the dossier. All 11
tasks lower; the full column flips. An adversarial skeptic then reproduced
the column from clean scratch and caught one real trust hole:
`[@@expect_failure]` lets a file whose only theorem is FALSE return
VERIFIED (definition checked-to-fail, silently dropped, exit 0, no Error
JSON, --report_assumes silent). The 22 lowered files were grep-clean and
byte-identical under regeneration, so the column stood; the token joined
the vacuity ban (verus external_body precedent) and the fix was
red-witnessed: both skeptic probes flip verified -> vacuous, real files
unaffected. The final table (t/AGREEMENT.md) was produced by the shipped
adapter, after the fix.

**The matrix: FULL AGREEMENT, 77/77 cells (11 tasks x 7 kernels), zero
flakes, exit 0, ~8 min wall via run_par.py.** Seven independent proof
kernels, two SMT-via-Boogie-style (dafny, verus), two SMT-via-Why3/WP
(spark, framac), one SMT-native (fstar), two kernel-checked proof-term
(lean, rocq), agree on every task and refute every twin.

**x86_64 tup: GO, gated on one admin line.** Probe report at
`tup/X86-FEASIBILITY.md`: /dev/kvm is root:kvm + gdm ACL and this user is
not in `kvm` (fix: `sudo gpasswd -a user kvm`, the lab administrators);
KVM guest is the recommended path. TCG works today at a measured ~14x per
thread (honest proxy benchmark, method recorded); rootless chroot is
measured dead (apparmor_restrict_unprivileged_userns=1, uid_map EPERM).
qemu-system-x86_64 10.1.3 + firmware now installed beside the aarch64
target, same prefix, same source hash.

New toolchain row:

    fstar: ~/.local/fstar/fstar/bin/fstar.exe (F* 2026.08.30, Z3 4.13.3 bundled)
