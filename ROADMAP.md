# tup and t: the roadmap

**Repo:** this repository, everything on `main`, private while its claims
move (verified 2026-09-04). **Focus:** t, the language seven proof kernels
grade, and tup, the receipted distro it will run inside. **Machine:** the
Dell, no root, seven kernels installed under `~/.local`; Windows measured
for five native kernels and all seven under WSL2 (t/RUN-ON-WINDOWS.md).
**Rule of the file:** hurdles with a DONE WHEN a third person can check,
never dates. Closed items are kept as a short record with their numbers
and a pointer to the witness; the argument that produced them lives in the
git history of this file (before 2026-09-05 for everything condensed
below).

---

## 0. Superseded: the srlm-forge plan (set aside 2026-09-02)

This file opened as the roadmap of srlm-forge, an 8B DPO pipeline (Track A)
and a from-scratch char-GPT laboratory (Track B, `locallm/`) unified as one
program in measurement-integrity engineering, with a paper (manuscript v15)
as its first report. Its plan was six MacBook workstreams (statistics core
and seed variance, contamination scans, manuscript claim binding,
declared-dialect provenance receipts, two preregistered MPS experiments,
Metal-arm prep), four GPU items (the re-execution campaign, an emulator
anchor, a version matrix, a third ruler), and a v16 of the paper.

On 2026-09-02 the focus moved to t and tup only; `forge/` and `locallm/`
are out of scope and nothing above is scheduled. On 2026-09-05 the paper
was re-decided as a t-first systems paper, with the DPO work reduced to one
paragraph citing v15 and tup to one paragraph. Two things from that era
still bind this file: the receipt discipline (a number is published beside
the instrument that produced it, and the instrument is pinned), and the
standing lesson that plans are claims and are checked against the bytes
before anything is spent on them. The full plan, its graveyard and its
reasoning are in this file's history.

---

## WS-7: The verifier gauntlet: multi-language verified pairs

**BUILT 2026-08-31.** Seven kernels, 77 of 77 cells `verified / refuted`,
zero flakes (`t/AGREEMENT.md`): Dafny 4.11.0, Verus 0.2026.08.30, GNATprove
FSF 16.1.0, Frama-C 33.0 with alt-ergo 2.4.3-free, F* 2026.08.30, Lean
4.33.1, Rocq 9.2.0, all installed without sudo from pinned hashed artifacts
and witnessed in `t/WITNESS-2026-08-31-dell.md`. `t/run_par.py` runs the
matrix cell-parallel and must diff byte-identical against `run_all.py`.

Three adversarial campaigns against t's own instruments produced WS-10:

- Adapter audit, seven hostile agents, one per kernel, each trying to make
  a FALSE theorem pass: about 38 holes with live probes (empty files and
  `verified==0` runs scoring VERIFIED, word-boundary escapes, axiom
  synonyms, an unbanned ACSL `axiomatic` block, output-parse injection).
  The repair inverted the trust model, from blocklisting mechanisms to
  requiring positive evidence that the named obligation was discharged;
  after one hardening wave and an independent re-attack, dafny, lean and
  rocq held (dafny survived 56 probes) and verus, spark, framac and fstar
  did not. The law that survived: semantic vacuity is not detectable by
  regex. Dafny is sound because its adapter asks the kernel
  (`--warn-contradictory-assumptions`) instead of grepping.
- Differential fuzzing of the lowerings (`t/fuzz_lower.py`, 218 tasks, about
  3,500 kernel runs): two lowering unsoundnesses (`lower_framac.py` and
  `lower_spark.py` lowered t's unbounded `int` to a machine word), three
  `lower_rocq.py` bugs, and SPARK folding "could not prove" into REFUTED.
- The twin discipline measured for the first time: all 81 INVARIANT-DROP
  twins load-bearing, but 21 of 119 COLLAPSE-IF twins computed the same
  value as the real program everywhere tested (10.3).

The Dafny pipeline (`dafny_verify.py`, `dafny_pairs.py`) was the
specification every adapter generalises: a five-way measured outcome
taxonomy (VERIFIED, REFUTED, MALFORMED, VACUOUS, TIMEOUT), a deterministic
resource budget with a hash-pinned toolchain fingerprint, flake-checking
before any verdict is trusted, and headless no-sudo installs. Nine
languages were dossiered and every dossier survived a hostile fact-check;
the matrix below is post-correction.

### 7.1 The matrix

| Language | Toolchain (pin) | Tier | Verdict taxonomy | Determinism | Corpus (shippable core) | One-line risk |
|---|---|---|---|---|---|---|
| SPARK 2014 | GNATprove FSF 16.1.0 tarball (bundles Why3 1.8.2, Z3 4.15.4, cvc5, Alt-Ergo — no COLIBRI); `--prover=z3 --steps=N` | A | Five-way measured (13-probe matrix, independently re-run); exit codes ambiguous — classify from phase errors + per-unit `.spark` JSON; `.spark` distinguishes countermodel from gave-up | `--steps` deterministic; fully self-contained tarball with published per-platform sha256 — best pinning story of the nine | SPARKNaCl (BSD-3), SPARKlib (Apache-2.0), spark_unbound (MIT); 4,422-test GPL suite local-only | Permissive corpus is an order of magnitude smaller than DafnyBench |
| Rust (Verus) | Verus release 0.2026.08.30.b432e82 (bundled Z3 4.16.0, Rust stable 1.97.1 via rustup) | A | Five-way measured via `--output-json` + rustc-JSON stderr; exit 0/1 only; rlimit-exhaustion hides inside the errors count — split by message text | `--rlimit` budget; `VERUS_Z3_PATH` + on-by-default solver-version check; every JSON run self-reports version/commit/toolchain | All-MIT: vstd, human-eval-verus (167 tasks; exclude `tasks/gpt/`), AutoVerus benchmarks, anvil, verified-storage | `assume`/`admit`/`external_body` verify anything at exit 0 — lexical ban on both halves, counted not dropped |
| F* | Official binary v2026.08.30 pinned per corpus; bundled Z3 4.13.3 via `--smt` + `--z3version`; `--report_assumes error` WITHOUT `--cache_off` (composed combination measured to fail every file — Prims' own axioms trip it) | A | Five-way measured incl. an end-to-end pair demo (7 flips + 1 survivor from one ulib file); both failure classes exit 1 — parse JSON diagnostics (19=refuted, 168/resolution=malformed, 335=vacuity); timeout shares error 19, split by message text | Same Z3 rlimit mechanism as Dafny (`--z3rlimit`×500k units), `--z3seed`, native `--quake` flake checker; three bundled Z3s make pinning mandatory | ulib+examples, HACL*, EverParse, steel, everquic (all Apache-2.0); FStarDataSet-V2 (CDLA-P-2.0, 54.4k definitions) | Frequent releases break corpora (FStar.Mul removed ~2026-04, not August) — F* version pinned per corpus, cross-version pairs never mixed |
| C (ACSL/Frama-C WP) | Frama-C 33.0 + Why3 1.8.2; Z3 (MIT) primary with alt-ergo-free 2.4.3 secondary — NOT opam `alt-ergo` 2.6.3, which is OCamlPro non-commercial; frozen why3.conf, `-wp-no-why3-detect` | A | Documented-measured, not yet executed: verdict lives only in `-wp-report-json` (exit 0 with unproved goals); `failed`=prover error→TOOL_ERROR, `invalid`=model-backed refutation, `unknown`=REFUTED, `stepout` distinct | `-wp-steps` is an explicitly machine-independent budget with its own verdict; pin `-wp-timeout` AND `-wp-smoke-timeout` (both default 2s wall) | ACSL by Example (MIT, maintained, targets 33.0); x509-parser BSD arm and Contiki-NG modules need porting | Three default-flag traps + the most fragile no-sudo install (opam `--disable-sandboxing`, source-built GMP, pre-existing gcc required) |
| Lean 4 | elan-pinned 4.33.1 (post-soundness-fix) + mathlib olean cache; leanprover-community/repl for throughput (Kimina server is stale and pins pre-fix v4.26.0 — do not adopt as-is) | A | Five-way measured + INCOMPLETE for holes; exit 0 ≠ verified (`hasSorry` gate, `#print axioms` allowlist); parse errors carry kind `[anonymous]` — text-match with parse-precedence, never kind-only | No SMT — architectural; `-DmaxHeartbeats` deterministic budget, but in-file `set_option` overrides the CLI (measured) — denylist required in v1 | mathlib4 (286k theorems), Compfiles, Lean Workbook, Batteries — all Apache-2.0 | Per-variant cost 10–100× Dafny without a resident-environment REPL; monthly toolchain churn invalidates receipts |
| Rocq (Coq) | opam `rocq-core.9.2.0` + `rocq-stdlib.9.2.0` (`rocq-prover.9.2.0` does not exist) + `rocq-mathcomp-boot.2.6.0` | A | Three-pass measured: `-vos` fail→MALFORMED, full compile fail→REFUTED, `rocqchk` axiom scan→VACUOUS vs VERIFIED (parse `* Axioms: <none>` — the section is always printed; rocqchk exits 0 even with axioms) | Architectural — no solver, 5/5 identical verdicts; only wall backstop is nondeterministic | MathComp core/fourcolor/odd-order (CeCILL-B), Iris/std++ (BSD-3); **analysis is CeCILL-C — local-only**; stdlib LGPL local-only | Ubuntu opam route hard-requires gcc (unconfirmed on the Dell) + `--disable-sandboxing`; per-corpus loadpath engineering |
| Agda | Official 2.8.0 single binary (one sha256 — no solver exists) + stdlib v2.4 at commit, `--safe` always | A | Measured: exit 0 / 42 / 251 + stable bracketed error names; INCOMPLETE class for holes; `--safe` refuses postulates and pragma smuggling ex ante with named SafeFlag* errors | Architectural; RTS heap cap (`-M`) as deterministic resource bound; single-binary fingerprint | agda-stdlib (MIT), cubical (MIT+BSD-3), agda-unimath (MIT), agda-categories (MIT) — ~960k LOC | Ablation unit is a syntactic step/clause, not a line — `find_hints` rewrite; hint density at scale unproven (the pilot is the tripwire) |
| Haskell (Liquid Haskell) | LH 0.9.14.1.1 on GHC 9.14.1 + **liquid-prelude** (omitting it breaks proof combinators) via package-env; PATH-shim-pinned Z3 4.15.8/4.16.0 | B | Rebuilt by hand: GHC exits 1 for everything — two-pass compile + message-class parse; `--json` in plugin mode is the highest-leverage unknown | No native rlimit — wrapper shim with cumulative per-module Z3 budget; solver `unknown` must be reclassified TIMEOUT from the shim log | LH test suite (BSD-3); benchmark suites per-suite allowlist ONLY — GPL hmatrix is vendored beside them under `tests/benchmarks/` | Three contract pillars (taxonomy, budget, vacuity) all custom; full GHC pipeline per variant |
| Whiley | wyc 0.10.18 + wyboogie 0.4.8 (`--noverify`) → raw Boogie 3.5.7 `/rlimit` + Z3 4.14.1 | B | Five-way from three stages + stdout regex — Boogie exits 0 on every outcome incl. parse errors; `/smoke` for VACUOUS, Boogie-level havoc for weak specs | Same substrate as Dafny (Boogie rlimit + PROVER_PATH), measured stable | Whiley2Boogie tests (Apache-2.0, ~1409 verifying programs); STD.wy is Apache-2.0 (dossier wrong) | Frontend dormant since 2022 — any bug is fork-and-own; hundreds of pairs, not thousands |

### 7.2 Rollout order: COMPLETE for tier A

All seven tier-A kernels landed and were measured on the box, each entering
only when its five-way taxonomy was measured here, F* last with an
adversarial skeptic reproducing its column from clean scratch. Still out,
deliberately: Agda (adapter measured and landed, lowering parked, because
its stdlib has no `lia` analogue and hand-plumbed proofs dressed as
automation are what t exists to refuse) and the B tier, Liquid Haskell and
Whiley (proven, low ceiling, Whiley's frontend unmaintained).

### 7.3 The adapter interface: `verifiers/<lang>.py`

What `dafny_verify.py` + `dafny_pairs.py` generalize to. One module per language, stdlib-only, importable by both the system Python and `.venv-train` (the dataset_gate rule). Each adapter must supply:

- **`Outcome`** — the five core outcomes plus `TOOL_ERROR`, extended only by measurement (Lean/Agda add `INCOMPLETE` for holes; SPARK may separate flow-analysis failures). Invariants: `ok=True` only for VERIFIED; TIMEOUT (including deterministic resource-out) is never folded into REFUTED; any unlisted diagnostic is TOOL_ERROR, never evidence.
- **`toolchain_fingerprint(budget) -> dict`** — sha256 of every binary in the verdict path (frontend, solver(s), and runtimes where present: JVM, dotnet, GHC), pinned library identity (stdlib commit, `.vo`/`.agdai`/olean cache), the budget, and the full flag list. Hardening flags (`--report_assumes error`, `-wp-smoke-tests`, `--safe`, `--warn-contradictory-assumptions`) live in the fingerprint; a run without them is a different, weaker instrument.
- **`verify_source(source, budget) -> Result`** / **`verify_path(...)`** — fresh temp dir per candidate, always: this one pattern defeats every cache trap found across the nine (Dafny obj reuse, gnatprove sessions, F* `.checked` digest hits, GHC recompilation avoidance, Agda `.agdai`). Classification constants cite measurements in the docstring, per house discipline.
- **`flake_check(source, n=3, budget) -> dict`** — n independent runs, verdict distribution. Mandatory before trusting any single verdict; mandatory cross-platform for near-budget pairs (heartbeat/step counts drift across arch).
- **`pair_verdict(chosen, rejected, budget) -> dict`** — chosen must be VERIFIED (never vacuous), rejected genuinely REFUTED. Refuses rejected-that-verifies, MALFORMED-as-rejected, and any half containing the language's trust holes (`assume`/`admit`/`magic`, `pragma Assume`, `postulate`, `Admitted`, `sorry`, `external_body`, option-pragma smuggling) — counted, not silently dropped.
- **`spec_strength(source, budget) -> dict`** — the weak-spec oracle where a body/spec split exists (Dafny havoc, SPARK `Import` function, F* `assume val` havoc, Verus `external_body` havoc, WP `any_int`, Boogie-level `havoc` for Whiley). Where the statement is the spec (Lean/Rocq/Agda) it is replaced by signature pinning plus trivial-arsenal/exfalso probes. Either way the function exists and reports weak/adequate/unchecked — silence is not a pass.
- **Pairs side** (`verifiers/<lang>_pairs.py`): `find_hints` with the language's ablation unit (whole line for Dafny/F*/Verus/LH/SPARK pragmas; period-terminated sentence for Rocq; step/clause/rewrite for Agda; tactic line or simp-list element for Lean), `drop_unit`, `pairs_from_file`, `subset_pairs_from_file` with budget accounting, `generate`/`write_jsonl`.

Acceptance rule for any new adapter: the language's measured probe matrix becomes its unit-test suite, and the survivor rate (the 26.9% analogue) is re-measured on that language's corpus before a single pair is minted. The Dafny numbers do not carry across; nothing is projected from them.

### 7.4 Not worth doing

- **Prusti.** Master and releases frozen since 2024-03, pinned to a 2023 nightly rustc, JVM+Viper stack. Verus wins on every axis. If Verus ever stalls, creusot/Kani need their own dossiers (Kani is bounded model checking — different verdict semantics, not a drop-in).
- **WyTP** (Whiley's native prover) — dead since 2020/2021. Boogie is the only path.
- **Kimina Lean Server as-is** — stale (~7 months), default-pinned to a Lean that predates the 2026 kernel soundness fixes. Drive leanprover-community/repl directly or fork-and-validate.
- **Exit-code-only classifiers, anywhere.** Dafny is the only language of the ten with a discriminating exit-code split. Every other adapter that shortcuts to exit codes silently merges MALFORMED into REFUTED or vacuous into VERIFIED. This is a standing code-review refusal on every port.
- **Statement-mutation pairs in Lean/Agda sold as proof pairs.** A mutated statement with a kept proof is an autoformalization/spec-writing pair — a different task. Proof-side mutations (lemma swap, rw flip, step deletion) mint the proof pairs.
- **Directory-glob corpus ingestion.** Twice the hostile checks caught permissive suites sitting beside GPL/unlicensed material in the same tree (LH `tests/benchmarks/` vendors GPL hmatrix; Whiley's WyBench is unlicensed). Per-suite allowlists only.
- **Known-bad flags:** F* `--proof_recovery` and `--n_cores >1` (the unsoundness issue closed in 2019, but there is no reward-path upside); SPARK `--level` ever and `--replay` in the gate; Frama-C defaults unpinned (2s wall timeouts, smoke off, prover auto-detect); Verus `--num-threads` unpinned; opam `alt-ergo` 2.6.3 (non-commercial license on the pipeline itself).
- **Nix, apt, or anything needing sudo on the train box.** Every recommended install above is a pinned tarball/zip, rustup, elan, ghcup, or opam `--disable-sandboxing` into `~/.local` — kept away from the provenance venv per the standing train-box rule.

### 7.5 Licensing appendix

Standing rule: shippable means permissive. Non-permissive corpora are usable locally for measurement; derived pairs never ship from the MIT repo (the CC BY-NC incident is the precedent).

**Shippable (permissive, verified at source):**

| Corpus | License |
|---|---|
| F* ulib + examples; hacl-star; everparse; steel; everquic-crypto | Apache-2.0 |
| FStarDataSet-V2 (HuggingFace) | CDLA-Permissive-2.0 |
| SPARKNaCl | BSD-3-Clause |
| SPARKlib | Apache-2.0 |
| spark_unbound | MIT |
| Whiley2Boogie tests; WhileyCompiler tests | Apache-2.0 |
| STD.wy (corrected — LICENSE in-tree since 2022) | Apache-2.0 |
| ACSL by Example | MIT |
| ANSSI x509-parser (BSD arm; archived, porting cost) | dual BSD/GPL-2.0 |
| Contiki-NG verified modules (per-fork annotation check) | BSD-3-Clause |
| Verus: vstd/examples, human-eval-verus (excluding `tasks/gpt/`), verus-proof-synthesis, anvil (MIT text verbatim), verified-storage, verismo, verified-ironkv, verified-node-replication | MIT |
| LH test suite; six named benchmark suites via per-suite allowlist (bytestring, vector-algorithms, esop2013-submission, icfp15, stitch-lh, cse230) | BSD-3 / MIT |
| liquidhaskell-tutorial | MIT |
| lh-workshop (corrected from "unverified"; eyeball LICENSE on ingestion) | BSD-3-Clause |
| mathlib4; Compfiles; Lean Workbook; Batteries | Apache-2.0 |
| miniF2F-lean4 (corrected: yangky11 fork is MIT; openai Lean folder Apache) | MIT / Apache-2.0 |
| LeanDojo Benchmark 4 (attribution required; prefer regenerating from mathlib) | CC BY 2.0 |
| MathComp core; fourcolor; odd-order | CeCILL-B |
| std++; Iris | BSD-3-Clause |
| agda-stdlib; agda-unimath; agda-categories | MIT |
| agda/cubical | MIT + per-file BSD-3 |

**Local-only or excluded:**

| Corpus | Why |
|---|---|
| FStarLang/pulse | No license file detected — all-rights-reserved until clarified |
| mitls-fstar | Custom license, SPDX NOASSERTION |
| AdaCore/spark2014 testsuite (4,422 tests) | GPL-3.0 — the volume corpus, local calibration only |
| spark-by-example | Unlicensed |
| Marmaragan; experimental-agentic-verified-software | Mixed/unverified terms — methodological references only |
| WyBench | Unlicensed — excluded even locally so no pair can trace to it |
| Frama-C WP regression suite (source tarball) | LGPL-2.1 |
| VerKer | GPL-3.0 (and AstraVer-targeted) |
| LH `tests/benchmarks/` outside the six allowlisted suites (hmatrix, nofib, xmonad, …) | GPL and mixed vendored code — never glob the directory |
| Rocq standard library | LGPL-2.1-only |
| CompCert | INRIA non-commercial — the exact CC BY-NC analogue |
| math-comp/analysis (corrected — dossier wrongly grouped it with CeCILL-B siblings) | CeCILL-C (weak copyleft) |
| Software Foundations | Admitted-riddled skeletons + authors' do-not-post-solutions request |
| the1lab/1lab | AGPL-3.0 |

---

## The far field

Direction, not tasks. Measured costs stand beside each entry so ambition never
impersonates a plan; nothing here reorders NOW or NEXT.

- **The provable-output model.** The training loop's reward becomes "a proof
  kernel accepted it," across every language WS-7 admits. What this makes
  provable is each emitted artifact — the model itself is not thereby a proven
  object; proving properties of the network is a different research program,
  and the writing never blurs the two.
- **t.** One spec interlingua over the WS-7 adapters — write a task once, lower
  it to Dafny / F* / SPARK / ACSL / Verus / LH, collect N independent kernel
  verdicts; cross-verifier disagreement becomes an instrument finding, this
  program's own genre. Prior art: Why3 (one spec language, many provers) and
  Viper (an intermediate verification language many frontends target). Trust
  path if t ever grows its own checker: CakeML-style — the checker is verified
  inside an established kernel (Rocq or Lean). A homemade language certifying a
  homemade system is two unaudited instruments signing each other's receipts,
  and it is refused here in advance.
- **The reproducible substrate.** Nix/Guix closures are the receipt discipline
  applied to the operating system — a content-addressed hash of the entire
  dependency graph, and D-3's version-matrix cells become one-line derivations.
  Guix's full-source bootstrap is the serious answer to trusting-trust. Slots
  behind WS-4; the receipts learn to record a closure hash.
- **An OS in t.** The measured price of one verified microkernel with mature
  tools and a team: seL4 — 8,700 lines of C, ~200,000 lines of proof, ~20
  person-years. It stays on the horizon until there is a team. The
  LFS-with-receipts build begun 2026-08-31 (Lima VM on the M5 Pro; every
  tarball sha256-manifested, every build command book-extracted and logged) is
  the pedagogical rung under this — a fully witnessed substrate, not a
  verified one, and labeled accordingly.

---

## WS-8: RESCOPED, tup is VM-native by decision (2026-08-31)

The generic kernel, initramfs, firmware and installer are deleted scope:
tup only runs virtualised, on the Dell as a KVM guest, so bare-metal work
had no consumer. Consequences, all landed: `tup/release.sh` ships a disk
image (qcow2, vmdk, vdi with hashes) and refuses one that has not reached
`tup login:` on a serial console; the kernel keeps its virtio set plus the
SATA and e1000 fallbacks, with VMware and VirtualBox labelled UNVERIFIED
until witnessed. Witnessed boots: QEMU/hvf on macOS (20 s), QEMU/TCG on
Ubuntu with no KVM (40 s), and the released split image on a second host
from its published parts (45 s under TCG,
`tup/receipts/boot-witness-dell-*.txt`), which also caught a stale digest
in SHA256SUMS and a boot command that mutated the image (RUN-ON-UBUNTU.md
now prescribes an overlay). x86_64 is GO and costed in
`tup/X86-FEASIBILITY.md`: KVM guest recommended, blocked only on the
account joining the `kvm` group; TCG works at a measured 14x per thread; a
rootless chroot is impossible under this kernel's userns policy. The
x86_64 leg is scripted and paused for KVM (5678f77, cbdb6d4, 2026-09-02).

## WS-9: going public: DONE 2026-08-31, private again by 2026-09-04

The repository went public on 2026-08-31 after the required scrub
(usernames in recorded paths to `user`, hostnames to roles, home paths to
`~`, third-party names to roles, author attribution kept) and a second
history rewrite on request that stripped every AI co-authorship trailer
(301 lines across 526 commits). The irreducible residue: `refs/pull/*`
still point at pre-rewrite commits and GitHub refuses pushes to them, so
the old history stays fetchable by SHA until GitHub Support collects them;
a rewrite is not an unpublish. The repository is private again while its
claims move (17.3); going public a second time is Treston's call at the
1.0 tag.

---

## WS-10: what t needs next — the audit's bill (opened 2026-09-01)

Everything here exists because something was *measured*, not because it
seemed like a good idea. Ordered by how badly it hurts the central claim.

### 10.1 Ground-truth fuzzing: DONE 2026-09-01, and it worked

Differential fuzzing compares kernels to each other and cannot see an error
all seven lowerings share. `t/truth_fuzz.py`, `t/boundary_probe.py` and
`t/metamorphic.py` grade against truth known by construction instead: a
postcondition built from the body's own semantics is KNOWN-TRUE, a mutated
one with an `interp.py` counterexample is KNOWN-FALSE, and every kernel
must verify the first and refute the second, with boundary tasks whose
truth differs between unbounded and machine integers and metamorphic
rewrites that must not move a verdict. Result: 1,009 task-instances, 7,063
cells; it found the definedness unsoundness in `lower_framac.py` (10.6) and
returned the null result the section was written for, no error shared by
all seven kernels across 357 known-false tasks, 48 of them true only under
a machine word. The oracle was earned: `interp.py` was validated against an
independently written second interpreter over 263,664 (task, input)
triples, that comparison was mutation-tested with ten seeded
misconceptions, which exposed two corpus blind spots, and a false claim in
`interp.py`'s own docstring was retired. What the null bounds: shared
error over t's current fragment at this corpus size, not agreement of the
lowerings.

### 10.2 Vacuity belongs in the lowering, not the adapter

Four adapters (verus, spark, framac, fstar) remain porous, and the reason is
now understood well enough to state as architecture: **an adapter that
re-parses a rich source language with regexes cannot be sound.** The
measured evidence is brutal — a Verus probe was defeated by a char literal
opening a phantom string, by a raw identifier `r#try`, and by a parameter
named `recommends`; its own canary check silently discarded a correct
vacuity reading; a Frama-C probe was suppressible by a sentinel the source
controls.

The harness *generates* the lowered file and therefore holds its AST. The
vacuity probe must be emitted there — a third artifact per task alongside
real and twin — so the adapter only ever runs what it was handed. That
sidesteps every parser hole at once. Defence against arbitrary hostile
source stays a bounded, honestly-stated claim: the adapters refuse the known
verify-anything constructs; they are not a sandbox.

### 10.3 Twin operators that guarantee a difference

21 of 119 COLLAPSE-IF twins were behaviourally identical to the real
program. `t/interp.py` now lets the harness *require a witness input where
real and twin differ* before a twin is accepted, and new operators
(off-by-one, comparison flip, guard drop, wrong-variable) exist to retry
when collapse-if is degenerate. What remains is to re-measure the strength
statistic on a fresh corpus and publish it beside the agreement table —
"the flip was measured" is only a claim once the twin is known to differ.

### 10.4 Grow the fragment, gate by gate

t is still integers, sequences, loops with invariants, and recursion via
spec funs. No heap, no floats, no concurrency. Each gate opens the same way
this one did: measure the taxonomy, land the lowering, have an adversarial
skeptic reproduce the flip table from clean scratch, and only then claim the
column. Floats are the most interesting next gate and the most dangerous —
every kernel's float model differs, which makes it the natural home for the
next cross-kernel disagreement finding.

### 10.5 The prove layer

`tup`'s prove layer is still unbuilt: the seven kernels run on the host, not
inside the distro. Building it puts the whole chain — spec, lowering,
kernel, libc, compiler — under one receipt discipline, and is the point at
which "a proof is only as good as the machine that checked it" stops being a
slogan in this repository.

### 10.6 Definedness: FIXED 2026-09-02

ACSL's logic is total, so `lower_framac.py` emitting no definedness
obligation let `at(s,-1) == at(s,-1)` prove by reflexivity; four witnesses
(negative index, one past the end, a `forall` and an `exists` whose range
includes `len(s)`), each at n=3. Fixed: the lowering emits the obligation
itself (`defs()`) in SPEC's evaluation order, `and`, `or`, `implies` and
`ite` guarding what they may not evaluate and quantifier bodies defined at
every range point. All four witnesses stopped verifying (three REFUTED, the
exists one TOOL_ERROR from a Why3 failure, never evidence) and the framac
column holds at 11 of 11 with twins refuted, flake n=3. Residual, in the
docstring: spec_fun bodies are axiomatised as total logic functions, so an
`at` inside a spec_fun applied outside its guarded range keeps the hole;
the committed tasks guard their ranges.

### 10.7 Purge incompleteness-sold-as-refutation: DONE 2026-09-02, the dafny door closed the same day

Ground-truth fuzzing measured 39 cells refuting tasks true by construction
(Verus on nonlinear arithmetic, Lean and Rocq treating "could not prove" as
disproof, Frama-C returning a goal whose own status was Timeout), every one
violating the rule `verifiers/__init__.py` states. Purged: every give-up
signal now mints UNPROVED (stopped without countermodel) or TIMEOUT
(budget fired), and REFUTED has exactly one door per column, positive
kernel evidence, either a countermodel the kernel confirms by execution or
a kernel-accepted refutation certificate (10.8's mechanism, adopted by
verus, framac, lean, rocq and, the same day, dafny). The certificate is a
parameterless lemma or expression function the lowering appends on twin
calls only, restating the harness's measured witness as a ground theorem
(value witnesses at the twin's result, exit witnesses at the measured
loop-exit state; preservation and undefined witnesses are not
certificated), minted REFUTED only when an isolated run discharges exactly
that certificate with no warning; a file naming it can never mint
VERIFIED. Dafny's door: exit 4 reads TIMEOUT on "out of resource" and
UNPROVED otherwise, and the lowering prunes operands t's short-circuit
semantics never evaluates so `--warn-contradictory-assumptions` does not
end the file. Measured 2026-09-02: all 11 dafny twins refute through the
lemma and every decoy (the name in a comment, a false certificate,
`requires false`, a second ensures, a parameterised or module-wrapped one)
reads UNPROVED; the full matrix is identical to the pre-change table with
dafny's 11 REFUTED cells carried by the certificate; the ground-truth
re-sweep (194 tasks, 1,357 cells, flake n=3) reads REFUTES-TRUE 0
machine-wide, and `gt_width_loop`, a FALSE task, is read non-pass by every
column for the first time. Cost: one extra kernel run per twin (1056 ms
against 1113 ms for the main run). The purge cost six flips: framac's
invariant-drop twins degrade to `verified / timeout`, correctly, because
their witnesses are loop-exit states and WP's step budget fires first.
Witnesses: `t/WITNESS-2026-09-02-refuted-purge.md`,
`t/WITNESS-2026-09-02-dafny-door.md`.

Residuals on the record: (1) `truth_fuzz.py` and `fuzz_lower.py` lower
without the witnesses they hold, so FALSE fuzz rows grade as
incompleteness in every purged column until the certificate protocol is
threaded through them as `harness.py` threads it through the suite. (2)
No adapter checks that a certificate's formula IS the negated spec at the
witness; that binding lives in the trusted lowering, so a hand-planted
certificate only ever demotes a real to REFUTED, and dafny's value-kind
certificate states the twin's result rather than evaluating it, unlike
SPARK's and Lean's. (3) The certificate names are protocol constants
(`t_refutation_certificate`, SPARK's `T_Refutation_Certificate`, framac's
`t_certificate`), emitted on twin calls only.

### 10.8 Restore SPARK's flip, honestly: DONE 2026-09-02, all 11 recovered

Nine of eleven SPARK twins read `verified / timeout` because gnatprove
could not produce a countermodel under the unbounded model. All 11 now
flip: `abs` and `max` keep their RAC-confirmed countermodels (hoisted above
the certificate, evidence signature unchanged), and the other nine are
refuted through the witness certificate `T_Refutation_Certificate` with
`Post => 'Result`, whose body is the negated spec at the witness ground
over the file's own twin, which gnatprove discharges in full. No cell
degraded and all 11 reals still verify. This is the protocol 10.7 handed
to the other columns.

### 10.9 Pin the loop frame rule in SPEC.md: DONE 2026-09-02

Gate 2 never said which variables a loop havocs, so a havoc-everything
lowering and an assigned-set lowering proved different theorems without
either looking wrong; the behaviour of an undefined `requires` was likewise
unstated. Both are now normative. A while loop havocs exactly the
syntactic assigned set of its body (AST-computed, nested targets count,
body-declared locals scoped out, intersected with the names in scope) and
preserves everything else with no invariant owed. The two-probe audit
found dafny, verus and framac already implementing it and fstar, lean,
rocq and spark threading every in-scope mutable through their encodings;
all four were fixed the same day, all seven verify both probes
flake-checked, and the emitted artifacts for every committed task are
byte-identical because every committed loop assigns every variable in
scope. Requires clauses owe definedness unconditionally, a task whose
requires is undefined at an admissible input is DEFECTIVE, and six of
seven lowerings surface it; framac is the recorded gap.

## WS-11: PROPOSED — the package-manager question, measured (opened 2026-09-02)

0.1 ships no package manager by design, and `tup/overrides/ch08/pkgmgt.sh`
records the decision rather than leaving it to be inferred. The audit in #17
prices that decision honestly: nothing maps a file to the package that
installed it, so no single package can be updated, removed, or CVE-patched
except by rebuilding. `receipts.jsonl` records what was *built*, not what
*landed where*.

This section is direction, not tasks. Nothing in it has been built or
measured; every candidate below is UNMEASURED and labeled so. What it
proposes is a way to answer the question with numbers instead of taste.

### 11.1 Ship pairs, not a menu

The tempting version — one image per package manager, let people pick — is
refused here in advance. N images means N builds, N receipt sets, and N
witness burdens, in a project whose README already enumerates what is
unwitnessed; multiplying the surface would grow that list, not shrink it.
Nobody chooses a distribution from a package-manager menu anyway.

The useful version is the same move `t` already makes. Every variant is built
**twice**: once **raw**, with no package manager, and once **managed**. The
raw build is the control, the managed build is the treatment, `inventory.sh`
diffs the two, and **the diff is the receipt**. This is the twin discipline
applied to the distro half — the real artifact beside a deliberately altered
one, where the measured difference is the finding. A package manager whose
cost cannot be shown as a file-level diff does not ship.

The deliverable is a table, not extra images:

    receipts/PKGMGR-COST.md
      manager   files added   bytes   new binaries   deps pulled in

Nobody publishes that number. tup is unusually well placed to: it has
`inventory.sh`, a known-complete 70,146-file baseline, and a layer mechanism
whose entire purpose is inventory-before → install → inventory-after.

### 11.2 The raw image is the reference, per variant

**Every variant keeps a no-package-manager build, permanently** — not as a
transitional state before a "real" one arrives. Raw is the reference build:
it is what the completeness claim is about, it is what a managed build is
diffed against, and it is the only configuration where "the filesystem is
the manifest" is true without qualification. If a variant has no raw twin,
its managed twin has nothing to be measured against and the number is gone.

### 11.3 Candidates per variant — all UNMEASURED

| Variant | Raw (reference) | Candidate manager | Why |
|---|---|---|---|
| **base** | ships raw, always | *none* | The control. Adding one here is what 0.1 already refused, and the refusal is the point. |
| **agent** | raw twin | `xbps` or `apk` | The layer needs the small userland an agent actually reaches for (git, curl, ripgrep, jq) and needs it to keep moving. Both are small, daemonless, single-binary, and FHS-shaped. |
| **train** | raw twin | `micromamba` / `uv`, **user-level** | Nobody compiles PyTorch or a CUDA stack. This is already the house practice — WS-7's install rules and the `qemubuild` micromamba env both work this way. A *system* package manager is the wrong instrument here. |
| **prove** | raw twin | toolchain-native (`opam`, `elan`, `rustup`) | Every kernel ships its own installer, and WS-10.5 already assumes them. A system manager would be a second, worse copy of seven working ones. |
| **infer** | raw twin | *none* | llama.cpp / vLLM are a static binary plus weights. Ship as a layer; a package manager buys nothing. |

Two constraints that bound the whole table:

- **Nix and Guix are not variants of this.** They replace the filesystem
  architecture (`/gnu/store`, `/nix/store`, no conventional `/usr/lib`), so
  they cannot appear as peers of `xbps` in a swap-one-component matrix.
  Their place is already recorded under "The far field" — closure hashes as
  the receipt discipline machine-enforced, Guix's full-source bootstrap as
  the serious answer to trusting-trust — and that entry stays where it is,
  slotted behind WS-4, with the receipts learning to record a closure hash.
  A Guix-based tup is a different operating system, and should be costed as
  one if it is ever wanted.

- **No foreign binary repository, for any candidate.** Every manager above is
  proposed as a *local package format and install tracker*, never pointed at
  an upstream repo. Foreign binaries are built against a different glibc, and
  the manager's database starts empty — it believes it owns nothing and knows
  nothing about the 70,146 files already on disk, so the first dependency
  chain overwrites base-system files with no record. That is precisely the
  unaccountable pile the README opens by refusing, and it would be reached in
  one command.

### 11.4 What is already measured, and what a first pass costs

Measured today, and the reason `pacman` is a poor first candidate despite
being the obvious one: of its build dependencies, `meson`, `ninja`, `gcc`,
`make`, `pkg-config`, `python3` and `openssl` are all present in the 0.1
image, but **`libarchive`, `curl`, `gpgme`, `libassuan` and `libgpg-error`
are all absent** (checked against `INVENTORY-RELEASE-0.1.txt`). So pacman's
row in the table would include an entire BLFS dependency chain — including
`curl`, which tup deliberately does not ship. That chain is arguably the most
interesting number in the table, and it is a reason to measure pacman, not a
reason to adopt it.

Also measured and relevant: `/usr/lib/locale/locale-archive` is 226 MiB and
kernel modules are 312 MB, against a 2.3 GB image — so "what does a component
cost" is already a question with large answers on this disk, and the
instrument to answer it exists.

UNMEASURED, and the honest first task: build one `tup/layers/pkg-<name>/`
following the `agent`-layer contract (MANIFEST with pinned sources and
sha256, `build.sh` with the inventory diff), for a single manager, and see
whether the diff is legible. One row of the table is worth more than the
whole design argument above. Needs an arm64 or x86_64 Linux build host;
X86-FEASIBILITY's GO verdict applies unchanged, since package management is
architecture-independent.

Cheapest thing on this page, and independent of every choice above: **the
`DESTDIR` install logs from #17.** They give the file-to-package map that the
missing manager would have provided, without writing or adopting one, and
they would make every row of the table above easier to produce.

## WS-12: the next six sessions (opened 2026-09-04)

WS-10 was the audit's bill. This is the queue that pays it down and then
answers the question the project exists to answer. Each session below is a
HURDLE with a stated done-condition, not a schedule: the order is what
unblocks what, and nothing here predicts a date.

**The 1.0 bar, so "done" has a number and a walk-through.** Two halves, and
a third person can check both. COVERAGE: at least half of the MBPP-DFY
subset of DafnyBench, 82 of its 164 programs, lifts into t and is VERIFIED
by all seven kernels with its twin REFUTED, published beside AGREEMENT.md
and reproduced from clean scratch by an adversarial reader per 10.4.
Deliberately the measured coverage, not the lexical one, which is why 12.1
came before everything else; the lexical count for that subset today is 25
of 164 (COVERAGE-dafnybench.md, family table). USABILITY, added 2026-09-05
when Treston set the bar at "fully usable in an IDE", with people coding in
Visual Studio and in VS Code: a person with a fresh checkout opens a `.t`
file in VS Code on Linux and on Windows, and in Visual Studio on Windows,
and gets highlighting, parse and well-formedness errors at the offending
token, hover with types and declarations, go to definition for a spec_fun,
formatting, and the seven kernel verdicts for the real task and its twin
with the witness shown, produced by the same harness that makes the tables.
The steps are committed as a walk-through and a second person has repeated
them. The road to both halves is "The road to 1.0" below; the tag is cut
when both hold.

**Where the numbers stand, 2026-09-04.** Lexical census: 77 of 643 gradable
DafnyBench programs in fragment, gate order array, div-mod, early-exit,
multi-return, array-mutation, zero-returns. MBPP measured separately over its
Python reference solutions: 62 of 974, gate order early-exit, div-mod,
string-char. Both corpora independently rank div-mod and early-exit at the
top, which is what makes those two the safe first constructs. Metamorphic
variance went 145 to 39 to a remainder of 10 as the adapter defects below
were closed.

### 12.1 Finish the metamorphic remainder: CLOSED 2026-09-04

Rewrites that cannot change meaning must not change a verdict. Variance
went 145, then 39, then 7, and the DONE WHEN's second clause holds: every
survivor is named here with the reason it is a property of the prover.
Six defects were fixed, none findable by comparing kernels against each
other: verus bound the letter `r` instead of the task's return name (40
cells); verus read `P || false` as vacuity (60); framac read unreachable
code as a dead contract (19); lower_framac emitted `--2` for unary minus
on a negative, C's decrement (10); dafny called a file MALFORMED that it
had verified, because exit 2 is both a parse failure and any warning (6);
and v0 verus literals carried no type, so non-negative literals inferred
`nat` against an `int` return, the one rewrite that turned MALFORMED into
VERIFIED. The larger movement was outside the headline: bases true by
construction that no kernel verified went 174, 154, then 0, and
incompleteness 152 to 90.

The seven survivors, all verus, all `verified -> malformed`: b053 mul-one,
b072 b083 b115 spec-add-zero, b093 b135 add-zero, b147 sub-zero. Each
rewrites a sequence index from `s[j]` to `s[j * 1]` or `s[j + 0]`, which is
no longer a trigger candidate, so verus refuses to infer a trigger for the
enclosing quantifier; dafny loses the same trigger and warns instead of
erroring. A property of syntactic SMT quantifier instantiation, which no
lowering or adapter change removes. Recorded, not repaired.

### 12.2 The F* naming defect: moved to 13.2

F* abstained on `gt_width_loop` because the task's name collided with an
F* keyword. fstar no longer refuses a name ending in `_loop` (69bfbe9,
2026-09-04), but the real done-condition, one sanitising pass shared by
every lowering with the rename recorded, is 13.2, where the lifter's
inventory raised the stakes: 68 of the 77 in-fragment DafnyBench programs
would hit fstar's uppercase-initial refusal.

### 12.3 The twins that verified: PARTIAL 2026-09-05, the decision is 13.3

`fuzz_lower` reports real-VERIFIED cells whose twin came back VERIFIED (16
lean, 16 rocq, 14 dafny, 14 spark, 13 verus, 9 fstar, 6 framac when
opened), each either a witness that does not witness or a vacuity probe
that missed, and the only open item touching a claim already published in
AGREEMENT.md. One defect fixed: the ladder accepted a twin on a witness
showing only that real and twin compute different VALUES, which does not
refute a loose `ensures`; interp already recorded the stronger fact as
`_ens` and `refuting_witness` existed for exactly this question, and the
acceptance path used neither. It now prefers a candidate whose witness
falsifies `ensures` and tags a merely-differing fallback `+nonrefuting`
(05b67b7). Re-measured: 97 verified-twin cells over 17 tasks, against 88
before, because the fix makes the weakness visible rather than removing
it: 3 tasks (10 cells) are deliberate vacuity probes that belong outside
the statistic, and 14 tasks (87 cells) are generated families (`v0loose`,
`v0if`, `v1bool`) carrying `_ens=False`, where seven kernels verifying the
twin is the correct answer. The statistic has been measuring the fuzzer's
spec strength, not the kernels' twin discipline. Whether the harness
refuses every task with no refuting twin, as SPEC.md says, is the
semantics call in 13.3.

### 12.4 The Dafny-to-t lifter

`coverage_census.py` decides fragment membership with regular expressions
over Dafny source. It needed three repair rounds and 185 confirmed detector
faults to become trustworthy, and it still answers a proxy question. The
lifter replaces it: a program is in the fragment when it LIFTS into a t task
and seven kernels verify it with the twin refuted. It also produces the task
corpus 12.5 and 12.6 both need, so it is the long pole.

Meaning preservation beats coverage. A program the lifter refuses with a
named reason costs one row in a table; a program it lifts wrongly corrupts
every number downstream. Parse, do not pattern-match: the census is the
standing evidence for what regexes do to this problem.

DONE WHEN: the lifter runs over all 785 programs, every emitted task
validates against SPEC.md and executes under interp.py, and the disagreements
with the lexical census are enumerated with a verdict on which instrument is
right in each case.

### 12.5 The ground-truth sweep

Run the lifted corpus through the full pipeline, seven kernels, real and
twin, flake-checked. This is the first coverage number that means what the
1.0 bar says, and the first honest answer to how far t actually reaches.
Expect it to be lower than the lexical 77: lifting can fail where a regex saw
nothing to object to.

DONE WHEN: a coverage table sits beside AGREEMENT.md giving verified-with-
twin-refuted counts per kernel over the lifted corpus, with the refusals
taxonomised into lifter gaps and language gaps.

### 12.6 The spec experiment

The whole training thesis is that a model can write a t task, specification
included, from a natural-language problem, and that seven kernels grading it
give a signal worth training on. That has never been measured once, which
makes it the highest-risk unknown in the project and the one furthest from
the critical path. It should move up.

The corpus exists: github.com/jonhhjackson-a11y/nl-problems, 24,748 problems
with 23,319 reference solutions, of which MBPP and HumanEval are already in
reach. The reward is not "did it verify": a vacuous specification verifies
trivially. The reward is the twin discipline, real VERIFIED and twin REFUTED
at a witness, which is the defense most verifiable-reward setups lack. The
test cases give a second, independent check that the specification is the one
the problem asked for.

Run generation on local models on the GPUs, which are idle for this project
and cost no API budget.

DONE WHEN: a measured table of how many model-written t tasks verify with a
refuted twin, and how many of those also pass the problem's own test cases,
because those two failures are different and both matter.

### 12.7 Constructs, in the measured order

div-mod and early-exit first, since both censuses rank them top
independently. They are largely disjoint in the lowerings, so they can run in
parallel worktrees rather than in sequence. Then arrays with mutation, which
is the expensive one: element-level framing has to replace name-level framing
in six of the seven loop encodings, and that is the exact class of bug the
2026-09-02 frame-rule fix caught one level up.

The known cross-kernel hazards, from the lowering survey: div-mod rounding is
a three-way split, Euclidean against truncating against floor, and division
by zero repeats the definedness story that framac's total logic already lost
once. Early exit splits the seven into three with a statement return and four
with none, so an outcome-flag encoding changes the invariant shape every
kernel proves.

DONE WHEN: each construct is in SPEC.md with a semantics stated for every
column, lowered in all seven, and an adversarial reader has reproduced its
flip table from clean scratch. Per ROADMAP 10.4, not before.

### 12.8 Standing items

Surface syntax landed 2026-09-04 (`t/surface.py`, round trip verified on
1528 tasks both directions plus 100,000 random ASTs), wired into nothing
on purpose; 14.1 is the decision.

Em-dash debt in the parts under focus, measured 2026-09-05: 526 in `t/`,
289 in `tup/`, 149 in the root markdown, 121 files, 72 of them
in this file. Repair the sentences the dashes were carrying rather than
deleting the character, which leaves run-ons behind; the closed items
above were rewritten without them on 2026-09-05, the open ones still
carry theirs.

`forge/` and `locallm/` remain out of scope.

## The road to 1.0 (opened 2026-09-05)

WS-12 is the next six sessions. This is everything after them, to the two
halves of the bar above. Hurdles, not dates: each carries a DONE WHEN a
third person can check and says what it unblocks, and the order is what
unblocks what. First cut, written 2026-09-05 from the repository as it
stands; a mapping pass over the repo refines it in a later commit, and any
number below that is not yet measured says so.

**Where the tool stands.** The notation exists: `t/surface.py` parses the
written form to the JSON AST and prints it back, round trip verified on 1528
tasks both directions and 100000 random ASTs. It is wired into nothing:
`run_all.py` and `run_par.py` read only `t/tasks/*.json`, a parse error
carries no line or column (the tokens do, the error does not), the
well-formedness checker `check_wf` lives inside `fuzz_lower.py`, and there is
no command, no language server, no editor extension and no formatter
command. `TUTORIAL.md` lesson 0 still says nothing parses the pretty form,
which has been false since 2026-09-04. Kernels: seven on Linux, installed on
the Dell without root; five native on Windows and all seven under WSL2
(RUN-ON-WINDOWS.md); macOS unmeasured.

### WS-13: the language

#### 13.1 Constructs to the coverage bar

12.7 opens div-mod and early-exit first, then arrays with mutation, in the
census order. The coverage half needs whatever the 164 MBPP-DFY programs
need, and that profile is UNMEASURED as a subset: the census ranks gates over
all 643 gradable programs, and 25 of the 164 are in fragment today. Measure
the gate order over the 164 alone before opening a gate for them. Every gate
follows 10.4: taxonomy measured, lowering landed in all seven, flip table
reproduced from clean scratch by a skeptic, then the column is claimed. The
hazards named in 12.7 stand.

DONE WHEN: the census over the 164 shows at least 82 lexically in fragment
AND the lifter (12.4) lifts them, each opened construct having passed 10.4.
UNBLOCKS: 16.2.

#### 13.2 Names in all seven columns

12.2's real done-condition. fstar no longer refuses a name ending in `_loop`
(69bfbe9), but only fstar, rocq and spark carry a RESERVED set, fstar
refuses an uppercase initial, and the lifter's corpus inventory (2026-09-05)
found that 68 of the 77 in-fragment DafnyBench programs would hit that
refusal. A lowering may refuse what it cannot express; it may not refuse a
name it can rename. One sanitising pass, shared by every lowering, recording
the rename so a table can still be read against the source.

DONE WHEN: a probe task named for each kernel's reserved words, and one with
an uppercase initial, lowers and runs in all seven columns.
UNBLOCKS: 12.4, 15.1.

#### 13.3 What a verified twin means

12.3's open decision, Treston's to make: SPEC.md says a task whose twin
verifies has a decorative spec and is REFUSED, and the harness does not yet
refuse it, so `no_flip` measures the fuzzer's spec strength rather than the
kernels' twin discipline.

DONE WHEN: SPEC.md states the rule taken, the harness enforces it, and the
fuzz_lower statistic means only what it says.
UNBLOCKS: 13.4, 16.1.

#### 13.4 The spec freeze and the conformance probes

`"t": 0` is frozen and `"t": 1` is a superset. 1.0 freezes the version the
tag ships, states every semantic decision taken since (definedness, the
frame rule, the twin rule, div-mod rounding, early exit, arrays) in SPEC.md,
and turns the hand-built probes of `fuzz_lower.py` plus the named metamorphic
survivors into a conformance suite every lowering must pass. The far field's
rule is unchanged: t ships a well-formedness checker, not a proof checker,
so nothing here needs mechanizing before 1.0; the day t grows a proof
checker, that checker is verified in Rocq or Lean first.

DONE WHEN: a versioned SPEC.md, a probe suite that runs in one command, and
all seven lowerings passing it in AGREEMENT.md.
UNBLOCKS: 17.2.

### WS-14: from a JSON tree to a language you type

#### 14.1 `.t` becomes the input

12.8 called this a decision, not a tidy-up. The decision this roadmap
assumes: `t/tasks/` holds `.t` files, the JSON is derived and never edited,
and the harness reads the notation. The round trip is what makes this safe:
`parse(print(t)) == t` on every committed and generated task.

DONE WHEN: every task in `t/tasks/` is a `.t` file, `run_all.py` and
`run_par.py` read them, and AGREEMENT.md regenerated through the notation is
identical row for row to the JSON run.
UNBLOCKS: 14.2, 14.4, 15.2.

#### 14.2 Errors with a position

`SurfaceError` names what went wrong and not where. Every parse and every
well-formedness error carries file, line and column of the offending token,
and names the SYNTAX.md production or the SPEC.md rule.

DONE WHEN: a committed corpus of malformed `.t` files, one per production and
one per check_wf rule, each yields its expected line, column and rule in a
test.
UNBLOCKS: 14.4, 15.2.

#### 14.3 The checker as a module

`check_wf` moves out of the fuzzer into a module of its own, imported by the
fuzzer, the surface parser and the command, with each error naming the
SPEC.md rule it enforces.

DONE WHEN: the module exists, `fuzz_lower.py` imports it, and the metamorphic,
truth_fuzz and fuzz_lower sweeps report the same numbers as before the move.
UNBLOCKS: 14.4, 15.2.

#### 14.4 One command

A single entry point with subcommands: parse, check, format, lower (one
kernel or all), verify (a chosen kernel set, flake-checked), twin (the
operator chosen and its witness), explain (what a verdict means, per
kernel). Output has two forms: text for a person and JSON lines for an
editor, one record per diagnostic with file, line, column, rule, severity
and kernel. Runs on Windows with `--flag=value` forms per RUN-ON-WINDOWS.md.

DONE WHEN: every subcommand has a test, and AGREEMENT.md produced through the
command is byte-identical to `run_par.py`'s modulo the timestamp.
UNBLOCKS: 15.1, 15.2, 17.1.

#### 14.5 Docs that are true

TUTORIAL.md, README.md, SYNTAX.md and SPEC.md agree with the tool and with
each other; every example in them is executed.

DONE WHEN: a doc test parses and checks every `.t` example in the four files
and fails on a stale sentence about the notation.
UNBLOCKS: 17.2.

### WS-15: the editors, Visual Studio and VS Code

#### 15.1 The harness as a library, with a cache

An editor cannot shell out to `run_par.py`: it needs verify(task, kernels)
callable in-process, verdicts cached by source sha256, kernel version and
budget so an unchanged task costs no kernel run, and the run lock relaxed
so an editor session and a table run can coexist without corrupting `out/`.
The flake discipline is not relaxed: the editor shows a verdict as
provisional until n=3 agree, and nothing provisional is ever written to a
table. Interactive budgets per kernel are UNMEASURED; AGREEMENT.md records
verdicts, not wall times.

DONE WHEN: cached re-verification of an unchanged task runs no kernel; an
editor session and `run_par.py` run at once and AGREEMENT.md is unchanged.
UNBLOCKS: 15.2, 15.5.

#### 15.2 The language server

One server, spoken to over stdio in the Language Server Protocol (JSON-RPC
with Content-Length framing), in Python 3.12 with the standard library only:
open, change and save notifications, publishDiagnostics from 14.2 and 14.3,
hover with the type and declaration of a name, definition for a spec_fun,
document formatting through the printer, and a custom notification carrying
kernel verdicts from 15.1 as they arrive. One server serves both editors.

DONE WHEN: a committed transcript of request and response pairs replays as a
test, and every diagnostic lands on the token 14.2 names.
UNBLOCKS: 15.3, 15.4.

#### 15.3 VS Code

An extension: a TextMate grammar for the notation, a client for 15.2,
settings for kernel paths and the kernel set, packaged as a `.vsix` with the
user-local Node 22 already on the box.

DONE WHEN: from a fresh checkout on Linux and on Windows the committed
walk-through yields every behaviour in the usability half of the bar.
UNBLOCKS: 15.5, 17.2.

#### 15.4 Visual Studio

Visual Studio 2022 hosts language servers through its own client
extensibility, so 15.2's server is reused; the extension is a VSIX carrying
the grammar and a language client, and it can only be built and tested on
Windows with the Visual Studio SDK. This box is Linux; the build runs on
Treston's Windows machine or a Windows CI runner. Five kernels run natively
there and WSL2 gives all seven (RUN-ON-WINDOWS.md).

DONE WHEN: the same walk-through, in Visual Studio 2022 on Windows, with the
five native kernels, repeated by a second person.
UNBLOCKS: 17.2.

#### 15.5 Verdicts in the editor

Per kernel, real and twin, the witness rendered as the input or loop state
it is; an absent kernel shown as absent and never as a verdict; a
provisional verdict marked provisional.

DONE WHEN: the walk-through shows a task VERIFIED with its twin REFUTED, a
real task REFUTED with the kernel's message, and an absent kernel, and the
same task shows the same verdicts in AGREEMENT.md.
UNBLOCKS: 17.2.

### WS-16: the claims

#### 16.1 The lifter, the sweep, the spec experiment

12.4, 12.5 and 12.6 as written. The lifter's design was settled 2026-09-05
without the judge panel (`t/LIFTER-DESIGN.md`, `t/LIFTER-DECISIONS.md`,
raw designs under `t/lifter-design/`); the build is in progress and 12.4
records its numbers when the 785 have run.

DONE WHEN: as stated there.
UNBLOCKS: 16.2, 16.3.

#### 16.2 MBPP-DFY to half

The coverage half of the bar: 82 of 164 lifted and VERIFIED by all seven
kernels with twins REFUTED. 25 of 164 are lexically in fragment today; the
measured number after 12.5 is unknown and expected lower.

DONE WHEN: the coverage table beside AGREEMENT.md shows at least 82,
reproduced from clean scratch by an adversarial reader.
UNBLOCKS: 17.2.

#### 16.3 The next corpora

HumanEval and MBPP bodies from the nl-problems corpus named in 12.6, run
through the same pipeline, so the coverage claim is not a claim about one
benchmark.

DONE WHEN: a second coverage table, same format, over a second corpus.
UNBLOCKS: nothing on the 1.0 path; it is what 1.0 is measured against next.

### WS-17: the release

#### 17.1 Install stories per OS

RUN-ON-WINDOWS.md exists and was confirmed on a real Windows machine. Linux
has the Dell's no-root install recorded outside the repo; macOS is
unmeasured.

DONE WHEN: a committed install page per OS, followed from a fresh machine by
a second person, ending in the walk-through.
UNBLOCKS: 17.2.

#### 17.2 The tag

A 1.0 tag contains: SPEC.md at its frozen version with the conformance
probes (13.4), AGREEMENT.md and the coverage table regenerated from clean
scratch by an adversarial reader (10.4), the install pages (17.1), the
walk-through (15.3, 15.4), the licensing appendix (WS-7.5), the two
extensions from a release page, and docs that pass 14.5. Plain checkout,
standard library only; no package manager. Whether the seven kernels can run
in CI is UNMEASURED; until measured, the tables are hand-witnessed and say
so.

DONE WHEN: both halves of the bar hold and the tag is cut.
UNBLOCKS: 17.3.

#### 17.3 Going public

The repository is private today (verified 2026-09-04) and its claims move
while it is. The em-dash debt in 12.8 is paid before the tag, sentence by
sentence, not by deleting the character.

DONE WHEN: Treston's call; the roadmap assumes the 1.0 tag is the moment.

### Decisions for Treston

Each is assumed as stated until answered; answering otherwise changes what
is written above.

- 13.3: refuse a task whose twin verifies (assumed yes).
- 14.1: `.t` files become the input and the JSON is derived (assumed yes).
- Lifter semantics: decided 2026-09-05 in `t/LIFTER-DECISIONS.md` (nat as
  int plus non-negativity clauses, a read-only array as a seq recorded as a
  rewrite, `x in s` as a bounded exists, an assume in executable code
  refused, and fifteen more), each with the cost of reversing it.
- 15.4: which Visual Studio version (assumed 2022) and where the VSIX is
  built (assumed your Windows machine until a CI runner exists).
- Editors beyond the two (assumed none for 1.0).
- 17.3: when t goes public (assumed at the tag).

### Far field, unchanged

Mechanizing the normative core in Rocq or Lean, tup's prove layer with the
kernels inside the receipted distro (10.5), floats, an OS in t. Considered
for this road and left where they were.
