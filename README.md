# tup

**A Linux distribution built for AI work, where you can account for every byte
and `t`, a language whose programs carry machine-checked proofs.**

Most AI development environments are unaccountable piles. Nobody can tell you
what is actually inside their container, which weights are loaded, or what an
agent changed on disk last Tuesday. tup is the one where you can: every package
is built from hashed sources, every file in the system is inventoried, and every
layer says exactly what it added.

**Status: tup 0.1 boots.** From its own disk, under nothing but UEFI firmware
with no `-kernel`, no `-initrd`, no host help, to a `tup login:` prompt in 20
seconds, with Claude Code preinstalled and the exact file-level cost of
installing it recorded. Witnessed on macOS/QEMU, on Ubuntu under pure TCG
emulation with no KVM at all, and on Windows 11 both natively (QEMU 11.1,
21 s) and under WSL2 (27 s), by someone who was not the author. What exists, what does not, and what is merely
intended are marked as such throughout; that is the habit the whole project is
built on.

---

## The two halves

### tup the distribution

Built from source with a receipt on every step. No package manager: the
filesystem *is* the manifest, which is what makes "we know everything on this
system" a checkable claim rather than a slogan. Every command comes from the
Linux From Scratch book verbatim; every deviation is a separate, diffable file
that states why it exists.

See [`tup/`](tup/) for the build system, and [`tup/README.md`](tup/README.md)
for how it works and what it has already caught.

The intended shape is layered, each layer with its own inventory diff:

| Layer | What it adds | Status |
|---|---|---|
| **base** | kernel, libc, toolchain fully hashed | **built and boots**: 105 book pages, a receipt each, [boot witness committed](tup/receipts/) |
| **agent** | Node, Claude Code AI tooling as a first-class citizen | **installed and measured**: [4,844 files added, 1 modified](tup/receipts/LAYER-agent-FULL.md) |
| **train** | `locallm`, PyTorch train models on the box itself | `locallm/` exists; layer not yet built |
| **prove** | `t` and its proof kernels | all 7 kernels run on Ubuntu today (no sudo, pinned + hashed); layer not yet built |
| **infer** | local model serving | planned |

To boot it yourself on any Ubuntu box, VM or not:
[`tup/RUN-ON-UBUNTU.md`](tup/RUN-ON-UBUNTU.md): one apt-get, one qemu
command, measured at 40 seconds to login even without KVM. The image is a
2.3 GB qcow2 with its sha256 published beside it.

### t the language

`t` is a **specification interlingua**: write a task once signature,
preconditions, postconditions and lower it mechanically to established
verifiers, whose kernels supply every verdict. t proves nothing itself and is
trusted for nothing. That is the design, not a weakness.

**Seven independent proof kernels, and a verdict on either side has to be
earned.** The kernels verify all eleven real programs. They refute the
deliberately broken twins only on positive evidence, and under that rule 71
of 77 twin cells refute while six honestly time out, so the suite exits 1
([`t/AGREEMENT.md`](t/AGREEMENT.md)). That exit 1 is the finding, not a
failure: the table stopped reading 77 of 77 the moment 77 of 77 stopped
being true.

| Kernel | Stack |
|---|---|
| Dafny 4.11 | .NET + Z3 |
| Verus 0.2026.08.30 | Rust + Z3 |
| GNATprove FSF 16.1 | Ada + Why3 + Z3 |
| Frama-C 33.0 | C/ACSL + alt-ergo |
| F* 2026.08.30 | SMT-native + Z3 |
| Lean 4.33.1 | kernel-checked proof terms |
| Rocq 9.2 | kernel-checked proof terms |

A task counts only on a **measured flip**: the real program verifies *and* a
deliberately broken twin is refuted. A twin that still verifies means the
specification is vacuous, and the task is refused.

**The finding: REFUTED used to be minted from failure, and now it is minted
from proof.** VERIFIED here always required positive evidence, obligations
the kernel discharged, never a bare exit 0. REFUTED did not. Four adapters
read "I could not prove it" as "I disproved it": Verus scored a failure on
nonlinear arithmetic it disables by default, Lean and Rocq had marker lists
counting "omega could not prove" and "Tactic failure" as disproof, and
Frama-C returned a goal whose own status was `Timeout` and called it refuted.
Ground-truth fuzzing measured 39 cells refuting a task that was true by
construction. A REFUTED that is really "I could not prove it" is the exact
category error the project forbids on the VERIFIED side, and wherever a twin
rested on one the flip was never measured.

The fix gives REFUTED one door per column: positive kernel evidence, and
nothing else. That is a countermodel the kernel confirms by executing it, or
a **refutation certificate**. The harness already computes a concrete witness
input where the real program and its twin provably differ; the lowering now
restates that witness as a ground theorem, that the spec fails at that exact
input, and the twin is refuted only when the kernel accepts the proof. Two
guardrails keep it honest: a file carrying the certificate can never mint
VERIFIED, so planting one can only demote a verdict, and a certificate the
kernel rejects mints UNPROVED, never REFUTED. The reusable lesson is small: to
trust a "this is false", make the tool prove the falsity at a witness, do not
infer it from a failure to prove truth. Verus, Lean and Rocq re-earned all
eleven flips this way, SPARK recovered its nine lost flips, and the post-purge
ground-truth sweep measures zero incompleteness-sold-as-refutation in the five
purged columns and in F*. One door is left open and named rather than fixed:
the Dafny adapter still reads kernel exit 4 as REFUTED, and the same sweep
finds exactly one true task it mislabels; it is recorded as remaining scope in
[`ROADMAP.md`](ROADMAP.md) 10.7. See [`t/`](t/) and
[`t/AGREEMENT.md`](t/AGREEMENT.md) for the current cross-kernel table.

**That table is the least interesting thing here, and the project says so in
its own files.** The defect above, and the ones below, were found by running
three campaigns against t's own instruments, because seven kernels agreeing on
a mistranslated or vacuous spec proves nothing:

- **The adapter audit** told seven hostile agents to make a *false* theorem
  pass through each adapter. They found ~38 holes, each with a live probe:
  empty files scoring VERIFIED, word-boundary escapes (`sorryAx`, `tadmit`),
  Axiom synonyms (`Parameter`, `Conjecture`), and a decoy `Print Assumptions`
  that printed Rocq's closedness sentinel while the real proof's audit was
  withheld. After one hardening wave, **Dafny, Lean and Rocq are sound**
  against every probe; **Verus, SPARK, Frama-C and F\* are not yet**, and are
  labeled porous rather than quietly shipped.
- **Differential fuzzing of the lowerings** ([`t/fuzz_lower.py`](t/fuzz_lower.py))
  generated 218 random well-formed tasks and ran ~3,500 kernel invocations
  looking for cross-kernel disagreement, because seven kernels agreeing on a
  *mistranslated* spec proves nothing. It found two **lowering
  unsoundnesses** at the integer boundary, since repaired.
- **Ground-truth fuzzing** ([`t/truth_fuzz.py`](t/truth_fuzz.py)) closed the
  blind spot differential testing structurally cannot see: if all seven
  lowerings share one misconception, every kernel agrees and nothing is
  reported. Tasks are now generated with their truth known *by
  construction*, the postcondition built from the body's own semantics or
  falsified by an exhibited witness input, and each kernel is graded against
  **truth rather than consensus**. Across 1,009 tasks and 7,063 cells it
  found a real unsoundness (see below) and, as a bounded null result, **no
  error shared by all seven**. The oracle it grades with was itself
  validated against an independently written second interpreter over 263,664
  cases, and that comparison was mutation-tested with ten seeded
  misconceptions, because zero disagreements proves nothing unless the check
  can disagree.

The same refusal applies to t's own instrument: `run_all.py` will not conclude
from fewer than two present kernels. On a machine with none installed it
prints where it looked for each and exits, because agreement measured on
nothing is one opinion, or none. Kernels are discovered portably (env var,
then PATH, then known install globs); the repo pulled onto a fresh Ubuntu box
found an elan-installed Lean with no configuration at all, verified both tasks
and refuted both twins. [`t/run_par.py`](t/run_par.py) runs the same matrix
cell-parallel and must produce a byte-identical table; divergence between the
two drivers is a finding, not a nuisance.

Agda's adapter is measured and landed; its *lowering* is parked, because the
standard library has no decision procedure for t's arithmetic fragment and
hand-plumbed proofs dressed as automation would be exactly the unwitnessed
artifact t exists to refuse.

---

## Why these two things are one project

A proof is only as good as the machine that checked it, and a machine is only
as good as your knowledge of what is on it. t makes programs provable; tup
makes the ground they are proved on accountable. Neither is worth much alone:
a verified program on an unaccountable system is a proof about nothing in
particular, and an accountable system running unverified software is just
tidy.

The research that produced this discipline lives in [`forge/`](forge/): an
execution-verified DPO pipeline whose real finding was that roughly half of a
measured benchmark gain came from the measuring instrument rather than the
model. That work is **scaffolding, not law**: it taught the method, it is
written up in [`forge/docs/`](forge/docs/), and the distro and the language
are where the method goes next.

---

## What is honestly not true yet

- **tup is VM-native by decision, not omission.** It runs everywhere a VM
  runs, which is everywhere it will actually be used; a bare-metal installer
  is deleted scope, not missing scope. The kernel carries virtio plus
  SATA/e1000 fallbacks, so VMware and VirtualBox should boot it, but nobody has
  witnessed that yet, so it is not claimed.
- **tup is arm64 today.** On an x86_64 host it boots under emulation
  (measured: 45 s to login on the training box, 21 s on an i9-14900K under
  Windows, both from the released split image under pure TCG with no KVM). A native x86_64 build through the same
  driver and receipts has not been run; the feasibility probe is
  [`tup/X86-FEASIBILITY.md`](tup/X86-FEASIBILITY.md): GO via a KVM guest,
  currently gated on a group membership, with TCG measured at ~14x as the
  fallback and a rootless chroot measured impossible on this kernel.
- **tup 0.1 is witnessed, not verified.** Nothing here proves the kernel or
  libc correct. It records what was built, from which bytes, in what order.
- **Frama-C proved statements about UNDEFINED expressions; FIXED as of
  cb70ac4.** Measured 2026-09-01: `ensures at(s,-1) == at(s,-1)` verified,
  as did reading one past the end and a `forall` whose range includes
  `len(s)`. SPEC.md says `at(s,i)` is defined iff `0 <= i < len(s)`, and
  ACSL's logic is **total**: an out-of-range read denotes an unconstrained
  value, so `e == e` closed by reflexivity and the definedness obligation t
  requires was never emitted. A lowering defect, not a kernel defect, and
  fixed in the lowering: `lower_framac.py` now emits the obligation itself,
  following SPEC.md's own evaluation order, and all four measured witnesses
  stopped verifying. Residual, stated in that file's docstring: spec_fun
  bodies are axiomatized as total logic functions, so an `at` applied
  outside its guarded range inside a spec_fun body keeps the reflexivity
  hole. The committed tasks guard their ranges; the same total-logic
  softness in `requires` and invariant positions is recorded future work,
  and SPEC.md now states normatively what an undefined `requires` means.
- **REFUTED is earned now, with one door still ajar.** The purge described
  under "the finding" above put every column's REFUTED behind positive
  evidence. The honest cost is Frama-C's six invariant-drop twins, which read
  `verified / timeout` because their witnesses are loop-exit states rather
  than program inputs, so no ground certificate exists and WP's step budget
  fires first; those six cells are why the suite exits 1. One adapter was left
  unpurged and is named, not hidden: Dafny still reads kernel exit 4 as
  REFUTED, and ground-truth fuzzing finds exactly one true task it mislabels,
  recorded as remaining scope in [`ROADMAP.md`](ROADMAP.md) 10.7.
- **The integer-boundary unsoundness is FIXED and independently
  re-checked.** A boundary campaign built 48 tasks false over the integers
  but true under a machine word, and no kernel verified any of them. The
  original defect, for the record:
  `lower_framac.py` lowers a t `int` to a C `int`, so WP constrains every
  parameter with `is_sint32` and `x <= 2^31-1` is granted for free
  Frama-C has been answering a 32-bit question while SPEC.md says t integers
  are unbounded. The fuzzer's `fz_p_intwidth` is the witness: six kernels
  refute it, Frama-C verifies it. `fz_p_seqlen` is the same disease in the
  sequence model, and `lower_spark.py` carries its own variant. **Until this
  is fixed, "seven kernels agree" means seven kernels agree on the eleven
  committed tasks, which stay far from that boundary not that the
  lowerings are faithful translations of one spec.**
- **The twin discipline is weaker than the phrase "measured flip" suggests.**
  Measured over 200 generated tasks: all 81 INVARIANT-DROP twins are
  load-bearing, but **21 of 119 COLLAPSE-IF twins compute an identical value
  to the real program** everywhere tested. For those tasks the flip measures
  nothing, because there is no behavioural difference to detect. Mutation
  operators that guarantee a semantic difference are owed.
- **Four adapters are not sound against hostile input.** Verus, SPARK,
  Frama-C and F\* can still be made to score a false theorem VERIFIED,
  chiefly through *semantic vacuity* an unsatisfiable hypothesis
  (`requires 1 == 0`, a content-free `Post => (True)`, a non-well-founded
  ACSL definition) lets a solver honestly discharge an obligation that proves
  nothing. This does not affect the committed tasks, whose lowerings contain
  none of these constructs, but the defensive layer is porous and is not
  claimed otherwise. The architectural lesson is recorded rather than
  papered over: **an adapter that re-parses a rich source language with
  regexes cannot be sound** Dafny is sound precisely because its adapter
  asks the kernel (`--warn-contradictory-assumptions`) instead of grepping
  for words, and the remaining vacuity checks belong in the lowerings, which
  hold the AST, not in the adapters, which hold only text.
- **t is still small on purpose:** integers, sequences, loops with
  invariants, recursion via spec funs; no heap, no floats, no concurrency,
  two mutation operators. Expressiveness gates open with measurements, not
  intentions.

## Layout

| Path | What |
|---|---|
| [`tup/`](tup/) | the distribution's build system, overrides, receipts |
| [`t/`](t/) | the language, its lowerings, and its verifier adapters |
| [`locallm/`](locallm/) | train a model from scratch on your own machine (MIT) |
| [`ROADMAP.md`](ROADMAP.md) | what happens next, adversarially reviewed |
| [`forge/`](forge/) | the research pipeline and its instruments |
| [`forge/docs/`](forge/docs/) | manuscripts, review dossiers, port witnesses |

## License

[`locallm/`](locallm/) is MIT. The rest is the working research record;
third-party datasets keep their own licenses (KodCode is CC BY-NC and is never
redistributed from here; AceCode is MIT with attribution).

Copyright (c) 2026 Treston Malachi Cuzzort.
