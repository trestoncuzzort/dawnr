# srlm-forge: One Program, Two Instruments — Research Roadmap

**Repo:** this repository, everything on `main` · **Paper:** manuscript v15 (LaTeX tree kept outside the repo; Markdown chain at `docs/revision-2026-08-25/`) · **Hardware:** MacBook M5 Pro (MPS, no CUDA), ubuntu-box (GPU 0 only), the retired Windows 4090 box (artifact recovery only)

---

## 1. The unifying thesis

The two tracks and the paper are not a training project plus a toy plus a write-up. They are **one research program in measurement-integrity engineering for empirical ML**, whose central claim the paper already states: *an execution-grounded verdict is objective but not thereby trustworthy — instruments do not announce when they stop measuring, so the verdict channel must be treated as adversarial and every benchmark gain decomposed against the instrument's idiosyncrasies before attribution.*

The program has three components with distinct roles:

- **Track A (repo root)** is the *field site*: an 8B DPO pipeline whose real product is the catalogue of eight ways its own instruments kept emitting well-formed numbers after they stopped measuring, plus the gates built in response (hash-receipt dataset gate, pinned verifier, frozen ruler, preregistration, drift guard).
- **Track B (`locallm/`)** is the *controlled laboratory*: a from-scratch 3M–19M char-GPT where every mechanism the 8B pipeline can only observe twice (massive-activation optimizer corruption, seed-vs-function decoupling, disattenuation estimator behavior) can be swept parametrically in minutes on MPS, under the same preregistration discipline.
- **The paper** is the first report from the field site. Its most transferable contribution is the instruments, and they are currently *described*, not *shipped*.

The unification move, therefore, is not "merge two codebases." It is: **consolidate the shared instruments (receipts, ledgers, claim-binding, the prereg schema) into one internal provenance module, prove transfer by cross-gating each track with the other's missing instrument, and use each track to discharge the other's — and the paper's — named limitations.** Every surviving proposal is an instance of that move.

---

## 2. NOW — MacBook, this week, no GPU box

Ordered by evidence-per-effort. All CPU/MPS; nothing touches the Dell except two clearly-marked optional probes.

### WS-1: Statistics core + in-system seed variance *(hours; salvaged from the killed proposal)*

- Extract Welch/incomplete-beta-t from `analyze_run1.py` into `stats_core.py`; **add TOST** (it exists nowhere in the repo — the paper's TOST arithmetic was hand-derived) built on the same `t_sf`.
- Self-test against retained raw rows: `analyze_run1.py` already reproduces Table 1 exactly on this Mac (t=0.656, df=74.0, p=.5140); assert the published TOST values (.0024 / .0433 / .295) too.
- Run a synthetic-Gaussian Monte Carlo coverage certificate of both procedures (CPU minutes).
- Decompose seed-vs-replicate variance from the **existing** `hc-seed01..25` rows in `data/ruler_noise.jsonl` (11 seeds × 40 replicates, real instrument): between-seed SD of arm means 0.0054 vs within-seed 0.0319 → σ_seed ≈ 0.002. Run the 55 true-null seed-pair Welch comparisons for an in-system empirical FPR. This is the deliverable `OPEN-ITEMS.md:26-35` asks for, at zero GPU-hours, and it sizes Run 2.

### WS-2: Contamination transplant *(1–2 days; merges the two leakage survivors)*

Two scans, both verified runnable today from local files, both banked as witnesses in `docs/port-2026-08-24/` style:

- **Scan A — corpus vs ruler:** all 918 chosen/rejected halves of `data/dpo_pairs_capped.jsonl` (plus the 1,244-pair parent and `repair_pairs.jsonl`) against the 31 ruler payloads, loaded from `data/screen_results.jsonl` and re-verified against `ruler_frozen.json`'s `task_sha256` (**not** via `verify_frozen()`, which returns hashes only). Already smoke-run: 31/31 CLEAN, 0.0% overlap, 9.5–10.8 s CPU. The v16 sentence is bounded: "no verbatim or ≥74-char content overlap; paraphrase-level duplication out of scope (scanner's measured 0% rename recall)." Anchor to `body-1.tex:59` / `body-4.tex:15`, **not** Limitation 4. Important honesty note: the 918 pairs come from the 13 seed tasks, zero AceCode rows — this scan bounds one contamination mode, it does not settle AceCode-internal near-duplication.
- **Scan B — training pool vs ruler:** the 43-tid pool payloads vs the 31 ruler payloads. This is the scan that mechanizes `prereg_track_a_run1.json:91`'s disjointness claim *before* run 1 ever generates a corpus from that pool, and it is what the future gate field should carry — **per-task max shingle fraction, never the corpus-aggregate verdict** (one fully-leaked task ≈ 3% of shingles and would read CLEAN under the 20% threshold).
- **Direction 2 — gate Track B:** `train.py` already computes the leakage verdict inline; the real gap is refusal. Add refuse-on-CONTAMINATED and refuse-on-`verify_claims.py`-failure (computed at train time, sub-second), refusal reason appended to `runs.jsonl`. Do not refuse on a merely-absent verdict file — that breaks the beginner double-click flow.
- The canonicalized-identifier second pass (via `measure_bank_concentration`'s `_Canon` + `ast.unparse`, ~10 lines) ships as *diagnostic only* until it has a measured false-positive floor.
- Gate/schema integration into `dataset_gate.py` is **staged behind WS-4's dialect decision** — no receipt schema bump yet.

### WS-3: `verify_paper.py` — manuscript claim binding *(2–3 days)*

The Track B `verify_claims.py` pattern aimed at `~/Documents/research/v15-arxiv/tex/`:

- `paper_claims.json` manifest: Table 1 → `analyze_run1.py` recomputation; MDE/N → `prereg_track_a_run1.json`; dataset facts → `dataset_gate.load_verified()`; concentration → `bank_concentration.json`; mutant survival → `test_adequacy.json`; ruler sha → `ruler_frozen.json`. Note t/p/CI live in `body-2.tex:28` and Appendix A, not in `tables.tex:26-27`.
- **Corrected expectations:** both Table 1 arms now verify from retained bytes (the 40 null replicates were merged back at commit `eb6ff4b`), so the checker's *first genuine catch is the paper's own stale 5-of-40 retention disclosure* (Appendix C, Table 1 note, F3) — a live, publishable erratum on day one, and better evidence for the thesis than the originally-planned "archival" demo.
- Hash rule: content→CRLF canonical for the paper's printed digests (`85fc0bdc…`, `15770d4d…`), with raw digest + platform recorded alongside — otherwise every hash check false-fails against the LF checkout.
- Recall calibration against the 2026-08-22 dossier: denominator = the **29 CONFIRMED** discrepancies annotated in/out-of-scope for digit-binding (not all 42; 5 are refuted, 3 pending, several are wording disputes). The v3–v9 drafts are Markdown, so budget the second extraction frontend as real work, not incidental.
- Pin the artifact state the manifest binds (named commit) and say so in the census appendix. Output classes: machine-verified / archival / withdrawn — with the archival class honestly smaller than first advertised.

### WS-4: Provenance core *(3–5 days; merges the provenance-core proposal + "Three-OS Verdict Invariance")*

The single most consequential design decision, written against the **post-`fd90f97` world** (the live receipt is schema 5, LF-dialect, `python 3.12.10`, and the gate already passes on this Mac via `SRLM_VERIFY_PY` — the old "Mac fails closed / CRLF fixed point" framing is stale, including the memory note that encodes it):

- **Declared-dialect receipts:** the canonical dialect is a schema-versioned *field of each receipt*, not a fixed CRLF constant. The provenance core hashes `canonical(blob, receipt.dialect)`. The live LF receipt verifies unchanged with zero regeneration; the paper's printed CRLF digests survive as checkable historical values. Flagship test, parameterized both ways on one committed blob: `dpo_pairs_capped.jsonl` → `0bb9a659…` under `dialect=lf` (live receipt) and `85fc0bdc…` under `dialect=crlf` (paper). This is Failure 8's prescribed repair, landed — and it is *more* urgent than originally pitched, because the paper's printed digest currently dangles against the live receipt (exactly the "reads like tampering" failure the program documents), and default-config Windows clones now fail against the LF receipt: the dialect problem flipped platforms, it did not go away.
- **Placement:** the provenance core lives **at the Track A root**, private with the rest of the pipeline; locallm's own instruments (`verify_claims.py`, `leakage.py`, `runlog.py`) stay self-contained in the public subtree (one copy of each file per commit `7ec4071`). It must read schema-5 receipts backward-compatibly; no `SCHEMA` bump, no regeneration — that decision stays maintainer-gated per `docs/UBUNTU-BOOTSTRAP.md`.
- **Platform-aware `verify_py`:** replace the hardcode at `dataset_gate.py:116` and the five remaining duplicates (`poscontrol/run_interleaved.py:34` is already platform-aware), keeping `SRLM_VERIFY_PY` and fail-loud. Rewrite `tests/test_verifier_pin.py`'s Windows-venv precondition POSIX-aware rather than deleting it. This is hygiene now, not a blocker — the Dell has been running around it since 08-25 — but it is ~an hour and removes a standing trap. Use `dataset_gate.require_verified` for the green proof, **never** `verify_dataset.py`, which writes the receipt (line 221).
- **Pin Track B's own instruments:** a provenance receipt over `verify_claims.py`, `leakage.py`, `runlog.py`, the prereg JSONs and `exp_*.py`, with the red witness: edit `SHINGLE` → receipt flips to VERIFIER-CHANGED. This closes the survey's named gap (changing scanner constants silently changes what old verdicts meant).
- **Ledger transplant:** wire `verify_dataset.py` / `ruler_noise.py` re-verify paths to append to the provenance ledger so Track A's receipts stop being current-state-only snapshots.
- R-1 framing: machinery landed; formal discharge (eol normalization + one receipt regeneration under it + autocrlf probe) remains **the maintainer's explicit decision** — say "enabled," never "closed."

### WS-5: locallm science — two preregistered MPS experiments *(each ~1 day instrument work + <1 hr compute)*

**(a) Blockwise-Adam damage curve** (`locallm/optim8bit.py` + `locallm/adam_bound.py`), with all reviewer fixes applied:

- Bound constant is `C(β1,β2)·Σlr` with `C = max(1, (1−β1)/√(1−β2))` **= 1.0** at train.py's `betas=(0.9,0.95)` — not 3.16 — plus a decoupled-weight-decay displacement term for `wd=0.1`.
- Outlier injection **after** `clip_grad_norm_` (or inside the optimizer wrapper), pre/post norms logged; add an activation-injection arm so the natural activation-gradient coupling is represented.
- Vendor bnb 0.50.1's dynamic/udynamic qmaps from the Dell (hash-receipted) instead of writing linear absmax; quantize both moments for the parity arm; mirror `min_8bit_size` (locallm's 256-element layernorms stay fp32 in real bnb). Note `poscontrol/quantized_adam_emulator.py`, `adam_bound_scan.py`, `grad_witness_hook.py` already exist — extend, don't re-invent.
- Preregister the survey-null branch (massive activations are scale-emergent; 0.4M–19M may show none naturally) and the detection-margin refutation branch.
- Claim ceiling: "a controlled second-architecture demonstration the paper can cite as **partial** discharge of Limitation 3c" — full discharge needs the real-bnb anchor (see NEXT).

**(b) Regime-boundary sweep** (`exp_regime_boundary.py` + prereg), with the metric fixed:

- **Double-centered** per-bucket loss profiles (subtract bucket means and run means) — raw profiles are degenerate (bucket difficulty dominates, r≈0.99 everywhere) and the naive pilot gate would not catch it.
- Grid reshaped toward where from-scratch training actually breaks (1,2,4,8,12,16,24×; 40× kept as an expected-divergence arm), with "arm diverges" preregistered as a *stability* result, separate from functional disagreement.
- Honest deliverable: a locallm-native regime result bound into the README chain, plus the genuinely transferable piece — **calibration of the split-half Spearman-Brown disattenuation estimator** (when/why it exceeds 1.0 vs a many-replicate truth), which answers the paper's own r>1.0 caveat at `body-4.tex:88`. This is *not* F3 and does not locate the 8B boundary; write it as a companion study.
- Log the corpus's SUSPECT leakage verdict (content_frac 0.107) into `not_claimed`.

### WS-6: Metal-arm prep *(hours now; experiment gated on artifact recovery)*

Zero-regret staging for the re-execution arm on a third serving stack: install Ollama; pull `llama3:8b-instruct-q4_K_M` and check the blob against `sha256-8d2bf4416eb1…` (fallback: copy blob+manifest from the Dell's `~/.ollama`); pin a verifier ≤3.13 (`~/.local/bin/python3.12` = 3.12.10 matches the live receipt; 3.11.9 via uv if paper-matching is preferred — decide in the prereg, never 3.14, under which the typing mechanism does not exist); time a 2-replicate unbanked null smoke and **size N from the smoke before preregistering fixed N**. The gating milestone is recovering adapter `sha256-4107cf60` from the Dell or the retired Windows box (its own `srlm-forge` checkout); if both are dead, re-scope honestly to the positive-control pair (GGUF `2cf7e8cc…` already on this Mac) and drop the +0.55 replication claim. Metal rows go to the new device-fingerprinted ledger, **never** appended to `data/ruler_noise.jsonl`.

---

## 3. NEXT — ubuntu-box, GPU 0 only

Sequenced; respects UBUNTU-BOOTSTRAP etiquette (PhD work outranks, uv 3.12.10, venv rule, resumable chains under gpuguard).

### D-1: Run 2 — the re-execution campaign *(the single most quotable open item; ~1 overnight)*

Re-scoped around the one thing verified as **not** done: no banked row anywhere retains a completion, adapter hash, or model digest, so Limitation 3a's arm ("A re-execution arm would settle it and has not been run") is still unrun and unrunnable on banked data.

- First: check whether the 21 `hc-seed` adapters (or `rep1`/`rep2` checkpoints) were retained on the Dell. If yes, zero new training; if no, 2–3 fresh seeds (<1 GPU-hour total; liveness smoke at `--max-steps 2`, never 1 — the warmup defect trains 1-step runs at lr=0).
- Preregister `prereg_track_a_run2.json` (run-1 schema): **re-execution as primary endpoint** — every typing-only NameError failure re-executed once with the import prepended, both verdicts banked per row; strict verdict retained alongside per the eval.py DECIDED note. Fresh same-session null under the `(version, platform)` pooling key from GREEN-WITNESS-D. Retain every raw completion + adapter/model digest per row (closes Limitations 8–9 going forward, and makes the import-emission vs annotation-suppression mechanism answerable post-hoc from 12,000+ rows — retiring the 15-draw wrong-template probe).
- Second motivation, stated plainly in the prereg: the 21-seed hc campaign in `ruler_noise.jsonl` is **unpreregistered exploration**; this program's own discipline demands the confirmatory run be the preregistered one.
- Dropped claims (already superseded, per the stale-OPEN-ITEMS audit): "first 8B run," "first 8B export" (exports ran ~25× to serve the Dell arms), "fourth hardware row" (RTX 6000 Ada is already in v15), "gives seed variance its slot" (21 seeds banked; WS-1 already decomposed it).

### D-2: Emulator anchor session *(half a day, GPU 0, shared with D-1 scheduling)*

Real `adamw_bnb_8bit` on the tiny locallm model at 2–3 g-sweep points, same device as the emulator, identical fixed gradient sequences, step-matched — the anchor that converts WS-5a's curve from emulated to demonstrated, and the only piece of 3c-discharge that requires CUDA. Vendor the qmaps here.

### D-3: Version matrix *(10–14 GPU-hours over several sessions)*

{PEFT 0.14.0 vs 0.20.0} × {bnb 0.45.0 vs 0.50.1} at pinned trl 0.12.2/transformers 4.46.3, **one torch build fixed across all cells** (2.5.1+cu121, the channel-logged original) with the Python-version delta named as residual. Corrected inference direction in the prereg: a commission-class cell isolates the varied pair *and* excludes OS-necessity; an all-healthy grid concludes only "library versions are not sufficient on Linux at this torch pin" — it can narrow to, never exclude, OS (a healthy Ubuntu cell is the TDR hypothesis's own prediction). Assays per adapter: adam-bound scan, `export_adapter.py --verify` 50,000× control, and a **new** residualized-31-task behavioral classifier (healthy centroid from the committed Table 2b/Appendix C record — `compare_adapters.py` is weight-space and useless here; build the classifier on the Mac before Dell time). Either outcome is a v16 section: kill the library axis, or first isolation of the anomaly.

### D-4: Ruler v3 *(conditional; ~15–20 GPU-hours)*

Gated on D-1/D-3 reproducing a within-ruler-v1 retrain gain on this stack, and preregister that gate. Reframed as the *third* instrument (the "never-built second instrument" OPEN-ITEMS entry is stale — the 31-task ruler is the second). Half-day tooling first: parameterize `build_ruler.py`/`ruler_noise.py` per instrument so ruler v1's frozen receipt is untouched. The 17 ruler-side mined tids (7 oss-only — decide strata in prereg) are a shortlist only; mandatory n=60 re-confirmation under the Dell's recorded verifier fingerprint. Add a same-session ruler-v1 anchor arm so the typing-share comparison isolates the task draw. Settle the drop-k=3 estimand decision in this prereg before any screening GPU time. Honest bound: same corpus, same language — this tests instrument-draw dependence, not the corpus/language half of Limitation 4.

---

## 4. The manuscript — what v16 gains, and the second paper

**v16 gains, in order of impact:**

1. **The re-execution measurement** (D-1, and the Metal arm if the adapter is recovered): converts the abstract's own caveat from bound to measurement — worded as "a re-execution arm has now been run, on [this stack]"; the published 48–58% figures stay bounds forever (those completions are gone; Limitation 9).
2. **Failure 8 repair landed** (WS-4): the paper gets to write its own wished-for sentence — "published digests reproducible off Windows for the first time" — via declared-dialect receipts, with F4/F8's withdrawn-claim embarrassments converted into a completed finding.
3. **The claim census appendix + erratum** (WS-3): every number labeled machine-verified/archival/withdrawn, opening with the live catch (the stale 5-of-40 retention disclosure — the null rows are back). Partially answers Limitation 12's self-review circularity: the checker is a fixed mechanical list any reviewer can run.
4. **Content-level disjointness sentence** (WS-2), anchored at `body-1.tex:59`/`body-4.tex:15`, bounded to one contamination mode.
5. **Version-matrix section** (D-3), either outcome.
6. **Limitation 3c partial discharge + the free adapter check productized** (WS-5a + D-2), with the corrected bound constant.
7. **Disattenuation-estimator calibration** (WS-5b) answering the r>1.0 caveat at `body-4.tex:88`.
8. Housekeeping the audits surfaced: fix the `body-2.tex:96` ("first experiment") vs `appendices.tex:282` (F3, demoted) inconsistency; give orphaned Table 4 its prose pointer; update F7's "repair prescribed" if effective-config recording lands with D-1.

**Second paper: no.** WS-2 + WS-3 + WS-4 are internal instruments — they exist to harden this program's own results, and they are not a publication target. The damage curve (WS-5a + D-2) is a possible short workshop paper if the parametric curve is clean, but its natural home is a v16 section. The TRL/PEFT seed-ordering defect stays an appendix + upstream issue (finish the `main`-branch trace first), not a paper.

---

## 5. Repo and method mechanics

**Layout of the monorepo:**

- `locallm/` remains the public MIT subtree, self-contained (`sync_public.py` publishes `locallm/` only, so nothing at repo root is ever public). The provenance core stays at the Track A root with the rest of the private pipeline. One copy of every file, per the merge principle.
- Track A stays at repo root, un-published, with its licence fences intact: **KodCode (CC BY-NC) never leaves this machine; AceCode (MIT) ships with attribution.**
- New Track A rows (Metal, Run 2, matrix cells) land in the new device-fingerprinted provenance ledger. `data/ruler_noise.jsonl` stays byte-identical to the published record — it is a paper artifact now, not a live sink.

**Receipt policy:** the live schema-5 LF receipt is authoritative; the provenance core reads it backward-compatibly; the CRLF digests in the paper are checkable history via the dialect field. **Receipt regeneration remains an explicit maintainer decision** (UBUNTU-BOOTSTRAP rule), required only for the eventual schema-6 field carrying the pool-vs-ruler per-task leakage maxima — bundle that with the R-1 discharge decision so the receipt is regenerated once, not twice. Two standing traps, now documented: `verify_dataset.py` *writes* the receipt (use `require_verified` to check), and the memory note "srlm-forge provenance dialect" predates `fd90f97` and must not be re-imported as a CRLF-fixed-point design constraint.

**Shared instruments (what unifies):** one prereg schema with a single canonical negative-scope field (retire the `what_this_CANNOT_show` / `not_claimed` split); receipts fingerprinting data + measurement code + interpreter, bypass-free, parse-don't-validate accessors with coverage tests; append-only ledgers with the qualifying verdict beside every number. Both tracks already use all of it; the provenance core makes it importable.

**What stays separate, and why:** the verifier/executor (`forge.py` and the SQL domain's runtime) stays Track A's — execution-grounded verdicts are the field site's subject matter, not shared infrastructure, and `domains/sql`'s forbidden-to-import-forge rule stands. locallm's trainer and experiments stay self-contained and beginner-runnable — the WS-2 gate must refuse on bad verdicts, not on missing setup. The paper's tex tree stays outside the repo; `verify_paper.py` bridges by path and pinned commit.

**Hygiene backlog (cheap, do alongside NOW):** prune `OPEN-ITEMS.md` — the "No Track A prereg" entry (closed 2026-08-02), the CRLF-receipt entry (superseded by the LF re-verify), the "export untested on 8B" and "no real-base run" entries (superseded by the Dell campaign), and the half-decided greedy-anchor entry (greedy-free landed; drop-k=3 remains genuinely open, decided in D-4's prereg). Pin `requirements.txt` (10 unpinned names; declare bitsandbytes). Finish the TRL `main` audit row.

**The graveyard — killed, and staying dead:**

- **"Ground-truth calibration of Track A's statistics" (locallm as a statistics surrogate).** Dead for four independent reasons: the quantity it wanted to measure by surrogate is already measured *in-system, better* (hc-seed01..25: 11 seeds × 40 replicates on the real instrument); the correction factor is a function of σ²_seed/σ²_replicate and does not transfer across systems — sizing the 8B run from a 3M char-model's ratio is exactly the assumed-not-measured input the program forbids; `analyze_run1.py` contains no TOST, so the surrogate would have certified code that had to be written anyway; and 30 shared-checkpoint seeds give seed-limited pseudo-replicated FPR bars — the very Dodge/Bouthillier error the program's own council cites against others. Its salvageable parts were extracted into WS-1 (stats_core + TOST + Monte Carlo + hc-seed decomposition) and are *better* than the original: zero training, real instrument. Any future proposal to "calibrate Track A's statistics with locallm training runs" should be answered by pointing at `data/ruler_noise.jsonl`'s hc-seed rows and this paragraph.

**Standing lesson from the review cycle, worth institutionalizing:** four of ten surviving proposals were written against a repo state that had already moved (the LF receipt, the merged null rows, the Dell campaign, the built second instrument). The program's own remedy applies to its planning documents too — **plans are claims; check them against the bytes before spending on them.** WS-3's manifest and WS-4's receipts are how that becomes mechanical rather than habitual.

---

## WS-7: The verifier gauntlet — multi-language verified pairs

**STATUS: the gauntlet is BUILT. Seven kernels, 77/77 cells
`verified / refuted`, zero flakes** (`t/AGREEMENT.md`) — Dafny 4.11.0,
Verus 0.2026.08.30, GNATprove FSF 16.1.0, Frama-C 33.0 (alt-ergo
2.4.3-free), F\* 2026.08.30, Lean 4.33.1, Rocq 9.2.0, all installed
no-sudo from pinned hashed artifacts and witnessed in
`t/WITNESS-2026-08-31-dell.md`. `t/run_par.py` runs the matrix
cell-parallel and must diff byte-identical against `run_all.py`.

**And the table is the least interesting artifact here.** Three adversarial
campaigns were run against t's own instruments; what they found is the real
state of the project and the source of everything in WS-10 below.

- *Adapter audit.* Seven hostile agents, one per kernel, tasked with making
  a FALSE theorem pass. ~38 holes, each with a live probe: empty files and
  `verified==0` runs scoring VERIFIED (this class reaches the HONEST
  pipeline, not just adversarial input); word-boundary escapes (`sorryAx`,
  `tadmit`, `assume_specification`); Axiom synonyms (`Parameter`,
  `Conjecture`); an ACSL `axiomatic` block never banned at all; and
  output-parse injection, where a decoy `Print Assumptions` prints Rocq's
  closedness sentinel while the real proof's audit is withheld.
- *The repair inverted the trust model* — stop blocklisting mechanisms,
  require positive evidence the named obligation was discharged. After one
  hardening wave and an independent re-attack each, **dafny, lean and rocq
  are SOUND** (dafny survived 56 probes). **verus, spark, framac and fstar
  are not**, and the survivors share one root cause worth stating as a law:
  **semantic vacuity is not detectable by regex.** Dafny is sound precisely
  because its adapter asks the kernel
  (`--warn-contradictory-assumptions`) instead of grepping for words.
- *Differential fuzzing of the lowerings* (`t/fuzz_lower.py`, 218 generated
  tasks, ~3,500 kernel invocations) found what agreement was hiding: **two
  lowering UNSOUNDNESSES.** `lower_framac.py` lowered a t `int` to a C
  `int`, so WP granted `x <= 2^31-1` for free and Frama-C was answering a
  32-bit question while SPEC.md says unbounded; `lower_spark.py` carried
  the same disease in its sequence model. Also three `lower_rocq.py` bugs,
  and an adapter taxonomy violation (SPARK folded gnatprove's "could not
  prove" into REFUTED, breaking the rule that incompleteness is never a
  refutation).
- *The twin discipline, measured for the first time:* all 81
  INVARIANT-DROP twins are load-bearing, but **21 of 119 COLLAPSE-IF twins
  compute an identical value to the real program** everywhere tested. For
  those tasks the "measured flip" measures nothing.

The Dafny pipeline (`~/srlm-forge/dafny_verify.py`, `dafny_pairs.py`) is the specification: a five-way measured outcome taxonomy (VERIFIED / REFUTED / MALFORMED / VACUOUS / TIMEOUT), a deterministic resource budget with a hash-pinned toolchain fingerprint, flake-checking before any verdict is trusted, single-hint ablation kept only on a measured verified→refuted flip, spec mutation, permissive-only shipping, and headless no-sudo installs on macOS-arm64 and Ubuntu 24.04. Nine languages were dossiered and every dossier survived a hostile fact-check; all tiers below are post-correction (no tier was overturned, but several load-bearing details were — they are folded in here, not in the dossiers). Limits first: no Ubuntu install below was executed on the actual box except Dafny's; every "proven" claim is macOS-measured plus a verified self-contained Linux artifact, and step zero on the Dell is always to re-run the language's probe matrix there.

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

### 7.2 Rollout order — COMPLETE for tier A

All seven tier-A kernels landed and are measured on the box: SPARK, Verus,
F\*, C/ACSL on the SMT track; Lean 4 and Rocq on the proof-assistant
sub-track. The entry criterion held throughout — a language entered only
when its five-way taxonomy was *measured* on this machine, never merely
documented — and F\* was the last, with an adversarial skeptic reproducing
its column from clean scratch before it was claimed.

Still out, deliberately:

- **Agda** — adapter measured and landed, LOWERING parked. The stdlib has
  no `lia`/`omega` analogue, so the proof-synthesis template for the LIA
  fragment is a design problem, not a typing task. Hand-plumbed proofs
  dressed as automation are exactly the unwitnessed artifact t exists to
  refuse.
- **Liquid Haskell, Whiley** — B tier, opportunistic only. Everything is
  proven but the ceiling is low and Whiley's frontend is unmaintained.

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

## WS-8: RESCOPED — tup is VM-native by decision (2026-08-31)

The four gaps this section used to cost out (generic kernel, initramfs,
firmware, installer) are **deleted scope, not open work**. tup only ever runs
virtualized — including on the Dell, where it runs as a KVM guest on Ubuntu —
so bare-metal engineering had no consumer. The decision and its consequences:

- A VM-only distro ships a **disk image**, not an ISO with an installer.
  `tup/release.sh` produces qcow2/vmdk/vdi with hashes, and refuses to ship
  a qcow2 that has not reached `tup login:` on a serial console.
- The kernel keeps its compiled-in virtio set plus the SATA/e1000 fallbacks
  defconfig already gave it; VMware/VirtualBox should boot via those paths but
  are labeled UNVERIFIED until someone witnesses one.
- Witnessed: QEMU/hvf on macOS (20 s to login); QEMU/TCG on Ubuntu with no
  KVM at all (40 s); and, 2026-08-31, the **released split image booted on a
  second host** from its published parts — 45 s to `tup login:` under pure
  TCG (`tup/receipts/boot-witness-dell-*.txt`). That run also caught two
  defects in the release itself: a stale whole-file digest in SHA256SUMS
  (corrected and re-uploaded) and the fact that the documented boot command
  *mutates* the image, so RUN-ON-UBUNTU.md now prescribes an overlay.
- **x86_64 build: GO, and costed.** `tup/X86-FEASIBILITY.md` answers it with
  measurements — a KVM guest is the recommended path and is blocked only on
  the account joining the `kvm` group (one admin line); TCG works today at a
  measured ~14x per thread; a rootless chroot is measured impossible under
  this kernel's userns policy. `qemu-system-x86_64` is already built and
  installed beside the aarch64 target from the same hashed source. Training
  stays on the host OS where CUDA lives.

## WS-9: going public — DONE 2026-08-31

The repository is public. The scrub ran before the flip, as this section
required: usernames in recorded paths became `user`, hostnames became
`ubuntu-box`/`train-box`/`macbook.local`, absolute home paths became `~`,
third-party names became roles, and author/copyright attribution was
deliberately left intact. A second rewrite followed on request, stripping
every AI co-authorship trailer from the history (301 lines across 526
commits; prose that factually describes Claude Code as software *installed
by the distro* was left alone, because deleting it would falsify the
record).

The one irreducible residue, recorded because it is the kind of thing this
project refuses to leave unstated: **`refs/pull/*` still point at
pre-rewrite commits.** GitHub keeps PR refs permanently and refuses pushes
to them, so the old history remains fetchable by SHA through those refs
until GitHub Support garbage-collects them. Anyone who cloned in the
interval also keeps the old history. A rewrite is not an unpublish.

---

## WS-10: what t needs next — the audit's bill (opened 2026-09-01)

Everything here exists because something was *measured*, not because it
seemed like a good idea. Ordered by how badly it hurts the central claim.

### 10.1 Ground-truth fuzzing: DONE 2026-09-01, and it worked

Differential fuzzing (WS-7 status) compares kernels **to each other**, so it
is structurally blind to the failure that matters most to this project: if
all seven lowerings mistranslate the same construct the same way, every
kernel agrees, the table is green, and the fuzzer reports nothing. The
integer-width unsoundness was caught only because Frama-C happened to be the
odd one out. A bias shared by all seven is invisible to that method.

The fix is to stop grading against consensus and start grading against
**truth known by construction**:

- **KNOWN-TRUE by construction** — build the postcondition *from* the body's
  own semantics (if the body computes `if x >= 0 then x else -x`, then
  `ensures r == (if x >= 0 then x else -x)` is true for all inputs, with no
  appeal to bounded testing).
- **KNOWN-FALSE by exhibited witness** — mutate a known-true postcondition
  and have `t/interp.py` produce a concrete input where it fails. One
  counterexample is a sound falsity proof; a bounded search is not a sound
  truth proof, and the generator must never confuse the two.
- **The oracle:** every kernel must VERIFY every known-true task and REFUTE
  every known-false one. A VERIFIED on a known-false task is an
  **unsoundness** — the most serious finding available. A REFUTED on a
  known-true task is a lowering bug or, if the kernel merely gave up, a
  taxonomy bug (incompleteness must never be reported as refutation).
- **Boundary discrimination:** generate tasks whose truth *differs* between
  unbounded and machine integers. Any backend that verifies a
  "true-only-under-32-bit" task is silently using machine ints — an
  independent re-check of the WS-7 integer repair that does not trust it.
- **Metamorphic invariance:** semantics-preserving rewrites (variable
  renaming, reordering independent statements, `x + 0`, double negation)
  must not change any verdict. This also catches shared errors, and is cheap.
- **Validate the oracle itself.** `t/interp.py` is t-authored; if it shares a
  misconception with the lowerings it will bless the bug. It must be
  differential-tested against the kernels and against exhaustive evaluation
  on small domains before it is trusted as ground truth.

**RESULT.** Built as `t/truth_fuzz.py`, `t/boundary_probe.py` and
`t/metamorphic.py`; 1,009 task-instances, 7,063 cells. It found the
definedness unsoundness in `lower_framac.py` (10.6) and returned the null
result this section was written to obtain: **no error shared by all seven
kernels**, across 357 known-false-by-witness tasks including 48 built false
over the integers but true under a machine word. The oracle was earned, not
assumed: validated against an independently written second interpreter over
263,664 (task,input) triples, and that comparison then mutation-tested with
ten seeded misconceptions, which exposed two corpus blind spots before they
could hide a real bug. It also retired a false claim in `interp.py`'s own
docstring, whose cited cross-check turned out to be a clone differing only
by renames. What the null result bounds: shared error over t's current
fragment at this corpus size. It is not a proof that the lowerings agree.

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

`lower_framac.py` emits no definedness obligation, and ACSL's logic is
total, so an out-of-range element denotes an unconstrained value and
`at(s,-1) == at(s,-1)` proves by reflexivity. Four witnesses, each
reproduced at n=3: negative index, one past the end, a `forall` whose range
includes `len(s)`, and the matching `exists`. SPEC.md is unambiguous that
`at(s,i)` is defined iff `0 <= i < len(s)`, so this is a lowering defect.
The repair is to emit the definedness proof obligation explicitly instead
of relying on the target logic to have one.

**Fixed.** lower_framac.py now emits the definedness obligation itself
(`defs()`), following SPEC's own evaluation order: `and`, `or`, `implies`
and `ite` guard the definedness of what they may not evaluate, and a
quantifier body must be defined at every range point, for exists as much
as forall. Measured: all four wave-4 witnesses stopped verifying (three
REFUTED; the exists witness lands TOOL_ERROR because Why3/Alt-Ergo fails
with "bound variable in of_term" on that goal class, which is ok=False and
never evidence), and the full framac column holds at 11/11 verified with
twins refuted, flake n=3. Residual, stated in the docstring: spec_fun
bodies are axiomatized as total logic functions, so an `at` inside a
spec_fun applied outside its guarded range keeps the reflexivity hole;
the committed tasks guard their ranges.

### 10.7 Purge incompleteness-sold-as-refutation: the 39 purged 2026-09-02; the dafny door closed the same day

The SPARK fix was the first instance found, not the only one. Ground-truth
fuzzing measured 39 cells refuting a task true by construction: Verus on
nonlinear arithmetic (`x*(y+z) == x*y + x*z`), Lean and Rocq via
`REFUTED_MARKS` lists that treat "omega could not prove" and "Tactic
failure" as disproof, Frama-C returning a goal whose own status is
`Timeout`. Every one violates the rule `verifiers/__init__.py` already
states. Two consequences: a kernel's REFUTED cannot be used as evidence
against the oracle, and any twin flip resting on such a verdict was never
measured.

**Purged.** Every give-up signal the four columns had been selling as
REFUTED now mints UNPROVED (stopped without countermodel, without budget
exhaustion) or TIMEOUT (budget fired): Lean and Rocq renamed their
`REFUTED_MARKS` to `UNPROVED_MARKS` and demoted them, Verus demoted bare
`errors > 0`, Frama-C partitions unproved goals by the goal's own status.
REFUTED has exactly one door per column: positive kernel evidence, either a
countermodel the kernel confirms by execution or a kernel-accepted
refutation certificate (10.8's mechanism, adopted by verus, framac, lean
and rocq as well as spark). Full matrix re-run 2026-09-02: exit 1, 194 s
parallel, all 77 real cells still verified, 71 of 77 twins refuted on the
new evidence. The purge cost six flips: framac's invariant-drop twins
(all_nonneg, contains, count_matches, linear_search, seq_max, sum_upto)
degrade to `verified / timeout`, correctly twice over, because their
witnesses are loop-exit states rather than program inputs and WP's step
budget fires before any countermodel. A ground-truth re-sweep with
`truth_fuzz.py` (2026-09-02, `--mirror 16`, 194 tasks, 1357 cells, flake
n=3, 213 s) measures ZERO REFUTES-TRUE cells in the five purged columns
and in fstar. Exactly one remains machine-wide, and it is the one door
this wave did not touch: `verifiers/dafny.py` mints REFUTED on kernel
exit 4, which is could-not-prove, not a countermodel, and on
`gt_q_ex_lit` (true by construction; an existential the solver will not
instantiate unprompted) that door sells incompleteness as refutation.
Lean and rocq now honestly read unproved on the same task; spark, framac
and fstar verify it. Bringing the dafny door inside the law, with the
certificate protocol or with dafny's own countermodel reporting, was the
remaining scope of this item when the paragraph above was written.

**Dafny door closed, later the same day (2026-09-02).**
`verifiers/dafny.py` no longer maps kernel exit 4 to REFUTED: exit 4 reads
TIMEOUT on "out of resource" and UNPROVED otherwise, and `gt_q_ex_lit`,
lowered from the same instrument, now reads UNPROVED at exit 4 (ok=False,
0 verified, 1 error, no certificate present). REFUTED comes through the
certificate protocol only. On a twin call `lower_dafny.py` appends one
parameterless `lemma t_refutation_certificate()` whose single `ensures`
restates the measured witness as a ground theorem: for a value witness,
the ensures fails at the twin's result on that input; for an exit witness,
the twin's surviving invariants and the negated guard hold at the measured
loop-exit state and the ensures conjunction fails there (preservation and
undefined witnesses are not certificated, as in the other columns).
Bounded quantifiers are unrolled (cap 64) with the bound values restated as
conjuncts the kernel checks; seq witnesses are let-bound inside the
ensures, because an inline `[]` is a type error on 4.11.0; recursive
spec_funs get an interpreter-chosen `assert f(args) == v;` ladder in the
lemma body, which can only lose a certificate, never fake one. One step is
specific to this column and was forced by measurement: dafny proves the
index-in-range obligation of `s[(-1)]` under the false guard `(-1) >= 0`
from the contradiction, and `--warn-contradictory-assumptions` then ends
the whole file at exit 2, so the lowering prunes every operand t's
short-circuit semantics never evaluated and hoists each deciding operand as
a top-level conjunct; under the hoisted facts every rewritten node is
logically equal to the original, so the emitted formula entails the
verus-shaped one by propositional logic, not by the interpreter's word.
The adapter mints REFUTED if and only if an isolated
`dafny verify --filter-symbol=t_refutation_certificate.` run (the trailing
dot anchors the end of the name; a bare filter also matched a decoy
`t_refutation_certificate_extra`) exits 0 with every "Results for" block
of its text log naming exactly that lemma at outcome Correct and no
warning printed, while the kernel's own `--rprint` of the main run shows
exactly one unmodified `lemma t_refutation_certificate()` carrying exactly
one ensures clause and no requires, and every failing block of the main
run's text log is a plain `method`: the filtered run assumes callee
contracts without re-verifying them, so a failing helper lemma or a
non-terminating function used by the certificate is refused by that
attribution. A file naming the certificate can never mint VERIFIED.
Measured 2026-09-02 on dafny 4.11.0: all 11 twins refute through the lemma
(isolated run 1 verified, 0 errors; 2 verified where dafny splits a
well-formedness task off, on seq_max and linear_search), all 11 reals
verify, flake n=3 agreed on every cell; the honest abs certificate planted
in the verified abs real demotes it to REFUTED; the name in a comment, a
false certificate, `requires false`, a satisfiable requires, a second
ensures, a decreases clause, a method-, twostate- or least-typed
certificate, a parameterised one, a module wrapper and a
`lemma xt_refutation_certificate` decoy all read UNPROVED. Full matrix
re-run (`run_par.py`, 190 s parallel): every one of the 77 cells identical
to the pre-change table, the 11 dafny REFUTED cells now carried by the
certificate, exit 1 still for the six framac timeouts only. Ground-truth
re-sweep (`truth_fuzz.py --mirror 16`, same seed and corpus, 194 tasks,
1357 cells, flake n=3 with zero disagreements, 211 s): REFUTES-TRUE 0
machine-wide, UNSOUNDNESS still exactly 10.6's residual
(gt_def_specfun_bad, framac), and ALL-KERNEL rose from 0 to 1 on
`gt_width_loop`, a FALSE task every column now reads non-pass, because the
dafny exit-4 door had been the one column passing it. The dafny FALSE-row
cost is the same one the five purged columns already paid under residual
(1): 76 FALSE rows and 11 ill-defined rows moved from pass to incomplete
(unproved, exit 4), since the sweep lowers without a witness. The cost per
twin verify call is one extra kernel run, about the cost of the main run
(remeasured 2026-09-02 on the shipped adapter: isolated run mean 1056 ms
against 1113 ms for the main run with its rprint and text log, sequential
on an idle box, four twins x3). Witness: t/WITNESS-2026-09-02-dafny-door.md.

Residuals, on the record: (1) `truth_fuzz.py` and `fuzz_lower.py` call
`lower(task, body)` without the witnesses they hold for FALSE rows, so the
purged columns, dafny among them since the same day, can no longer mint
REFUTED on FALSE fuzz rows and those cells grade as incompleteness; if
FALSE rows should grade `pass` again, the certificate protocol has to be
threaded through the fuzz instruments the way `harness.py` threads it
through the suite. (2) The verus adapter, and the dafny adapter with it,
cannot check that the certificate's asserted formula IS the negated spec at
the measured witness; that binding lives in the trusted lowering, so a
hand-planted certificate in a passing real program mints REFUTED per the
protocol (declaring the name can never mint VERIFIED, so planting it only
demotes), and on dafny a content-free `ensures true` certificate is
kernel-accepted and reads REFUTED for the same reason (measured on the abs
twin). Dafny adds one binding of its own: a value-kind certificate states
the negated ensures at r := the interpreter's twin result, because a
method is not callable from a lemma, so unlike SPARK's `F(input)` and
Lean's applied function that result is trusted, not kernel-evaluated.
(3) The certificate names are protocol constants
(`t_refutation_certificate`, emitted by the verus, lean, rocq and, since
the same day, dafny lowerings; SPARK's `T_Refutation_Certificate`;
framac's `t_certificate`); the lowerings emit them only on twin calls,
where `harness.py` passes the measured witness.

### 10.8 Restore SPARK's flip, honestly: DONE 2026-09-02, all 11 recovered

Nine of eleven SPARK twins read `verified / timeout`: gnatprove verifies
the real program but cannot produce a countermodel for the twin under the
unbounded model. `abs` and `max` were recovered with a confirmed
countermodel (its small-step RAC actually executing it).

**Recovered, not verify-only.** All 11 twins now flip. `abs` and `max`
keep their RAC-confirmed countermodels (classification hoists that channel
above the certificate, so their evidence signature is unchanged); the other
nine are refuted through the witness certificate: `lower_spark.py`
restates the harness's measured witness as one extra expression function,
`T_Refutation_Certificate` with `Post => 'Result`, whose body is the
negated spec at the witness ground over the file's own twin, and gnatprove
discharges every check of it (severity info, VC_POSTCONDITION among them).
Emitted only on twin calls; the adapter mints REFUTED only when the kernel
discharges the certificate in full. No cell degraded: the nine went
TIMEOUT to REFUTED and all 11 reals still verify. The same protocol is what
10.7's purge handed to verus, framac, lean and rocq, and, later the same
day, to dafny.

### 10.9 Pin the loop frame rule in SPEC.md: DONE 2026-09-02

Gate 2 said only "the standard partial-correctness-plus-termination
package" and never stated which variables a loop havocs. A lowering that
havocs everything and one that havocs only the assigned set prove different
theorems, which is exactly how two lowerings drift apart without either
looking wrong. The behaviour of an undefined `requires` was likewise
unspecified. Both were found by the oracle-validation pass.

**Pinned, both.** SPEC.md Gate 2 now states the frame rule normatively: a
while loop havocs exactly the syntactic assigned set of its body
(AST-computed, if- and nested-while targets count, body-declared locals
scoped out, intersected with the names in scope), every other variable is
preserved with no invariant owed, and an empty-havoc loop is a refusable
shape. The two-probe audit (2026-09-02, a return assigned before the loop
and never inside it; a prefix local never assigned in the loop and read
after it) measured dafny, verus and framac already implementing the rule
and verifying both probes, while fstar, lean, rocq and spark threaded every
in-scope mutable through their loop encodings, the havoc-everything
theorem: lean and rocq scored both probes UNPROVED, spark TIMEOUT, fstar
REFUTED. All four were fixed the same day; with the fixes all seven kernels
verify both probes, flake-checked, and the emitted artifacts for every
committed task are byte-identical to before, because every committed loop
assigns every variable in scope. Undefined `requires` is likewise now
normative in the Definedness section: the clauses owe definedness
unconditionally, a task whose requires is undefined at an admissible
input is DEFECTIVE, and the
measured probe shows six of seven lowerings surface it; framac is the
recorded gap, per its docstring.

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
