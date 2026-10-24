# dawnr 6.0: the plan of record (2026-10-24, revised the same evening)

This file replaces `internal/ROADMAP-LOG.md`, deleted on 2026-10-24 at the user's request as stale. The log's
full text stays in git history (`git show a24d20a2:internal/ROADMAP-LOG.md`). What was still live in it is
carried into section 6. From today this file is the roadmap of record for the 6.0 release; `ROADMAP.md` at the
root is the public face and is updated as milestones finish.

The first draft of this plan, written the same afternoon, built 6.0 on the corrected 4,189-row set and read
candidates against a control that mixed two training sets. Section 2 records why both were wrong.

## 1. What 6.0 is

dawnr has shipped through one rolling channel whose model is dawnr v5. Since v5, five candidate lines were trained
or prepared and each was called a version: v6, v7, v8, v9 and v10. None was promoted. 6.0 folds all five into
versioned releases (the user, 2026-10-24: "drop the student and vN niche and just call it dawnr X.Y.Z"): 6.0.0 ships
now with the October 5 model unchanged, and each increment after it (6.1.0, 6.2.0, ...) ships a model only when it
passes the door of section 3. The number names the whole system, not a training run:

- the application at a tested revision, with `dawnr version` printing it;
- dawnr running smoothly on a laptop like the one it is built on (an RTX 5050 Laptop GPU with 8 GB, 16 cores,
  15 GB of memory), measured there as a release condition;
- the qualification protocol as code and as a document, so a model enters the release only one way;
- the instruments the five lines produced: the ceiling instrument and its gate precision, the three-decode report,
  the strict reference check (1,000 draws, both mutant families at 90%), the annotation held-out set;
- the data every useful line contributed, on v5's own base, trained on two seeds and read by the protocol;
- the model that passes that reading, or v5's weights under the 6.0 card if none does, said plainly;
- the receipts under `release/evidence/` for every number in the card.

The names v6 to v10 stay in the PREDICT records as the names of measured artifacts. Nothing is renamed in history.

## 2. What the records showed on 2026-10-24

**Every candidate since v5 trained on a different base than v5.** The published v5 trained on 5,095 rows (SHA-256
`848fca29…`, its model card; recovered 2026-10-11, `t/out/v5-rebuild-20261011/desktop-source-recovered.json`).
Every later candidate trained on a corrected set: `e14f766f…` (4,189 rows: the 3,352 of v5's rows that passed the
2026-10-11 audits, 1,315 uDebug rows of which 909 are judged by Python tests with no proof, and 406 recovered
student rows, deduplicated) or its corrective snapshot `8aa1b752…` (4,089 rows).

**The training-seed arm changed the rows too.** The model registered as "v5's exact rows with seed 2" trained on
`e14f766f…` (`t/out/v5s2-20261022/manifest.json`, `data_sha256`). Its readings compare a different training set on a
different seed against v5, so "a training seed alone moves the count by two" is not supported by it, and a control
built from v5 plus that model mixes two training sets.

**The 240-problem panel holds 34 problems v5's rows had matched.** It is the 95 development problems plus all 145 of
the wider reader's pool; `heldout_audit.wider_flagged()` marks 34 of the 145 as matched by the rows of 2026-10-05.
The clean development panel is the 95 plus `heldout_audit.wider_clean()`, 206 problems.

| reading | v5 (original rows, seed 1) | corrected set, seed 2 | paired, per problem |
|---|---:|---:|---|
| clean, mean of three decodes, 206 unleaked | 19.33 | 14.67 | v5 better on 12, worse on 8; sign p 0.50, permutation p 0.15 |
| all seven, the same | 8.67 | 6.33 | better on 4, worse on 2; permutation p 0.25 |
| clean, the 34 leaked | 10.67 | 8.33 | better on 6, worse on 4; permutation p 0.43 |

First decodes on the 95: v5 6 (three decodes 6, 4, 6), v6 on the corrected set 4, the seed-2 model 4 (4, 5, 4),
v9 (the corrected set plus 833 strict self-distilled rows) 7 on its one decode.

**Reading.** Every model on the corrected set sits at or below v5, and v5 leads it on the unleaked problems on
average, but no paired test separates them. A weaker base is likely and not proven. 6.0 does not need the answer:
it builds on v5's own rows and reads the result against the published v5 alone, on unleaked problems.

## 3. The door: how a model becomes the 6.0 model

Registered here and repeated with numbers in the candidate's PREDICT file before training. All five must hold:

1. **Paired reading on the 206.** The candidate's six decodes (two seeds, three decodes each) against the published
   v5's three, per problem, on the clean development panel (`t/out/release-6.0/dev-206.txt`, written in M1 from the
   95 and `wider_clean()`), with `t/recipes/three_decode_report.py`. More problems up than down, permutation p at
   or below 0.05.
2. **Gate precision.** On the ceiling instrument, the three-test gate's precision is at least 0.70 (v5 0.785).
3. **Given specifications.** At least 27 of the 33 held-out specifications proved by all seven kernels at Q8_0.
4. **Held-out 182, read once.** After 1 to 3 decide, the winner is read once on the clean 182 under the
   larger-inputs instrument (`t/score_levels.py --larger`) and must not fall below v5's 17 at one or more kernels
   and 12 at all seven. The held-out number never selects between candidates.
5. **Smooth on this laptop.** From a clean checkout on the laptop: `./install.sh`, `dawnr doctor`, and the README's
   example commands complete; the median command time and the peak memory are within 10% of v5's on the same
   machine; no software thermal slowdown is reported on the GPU during the run. v5's baseline is measured first
   (M1).

A mean is never a verdict. If no candidate passes, 6.0 ships v5's weights as the 6.0 model and the card says which
candidates were read and what they scored.

## 4. The candidates: 6.1.0 (A) and 6.2.0 (B)

**Base.** v5's 5,095 rows minus what today's policy refuses: the GPL lineage (`--refuse-gpl`; 61 rows built from
MBPP-DFY programs) and any row touching a panel in use (the held-out 182, the development 95, the wider clean 111,
the 33 specifications). Rows that match problems already out of the panels are kept, the standing policy recorded
in the v9 registration. The 2026-10-11 audit kept 3,352 of the 5,095 under the stricter rule of that day. Re-run 2026-10-24 under
today's policy: 62 rows refused (61 GPL lineage, 1 held-out problem 629 as a twin) and 9 more views of the refused
problems, 5,024 rows kept (`014e5a32…`, `out/release-6.0/base-families.json`). The uDebug rows stay out (they are one of the suspects; an ablation can test
them later).

**Added, each rebuilt against this base with `t/recipes/v8_spec_rows.py` (problems the base already covers are
skipped) and audited with `t/heldout_audit.py --panels --refuse-gpl`:**

- v9's strict self-distilled specifications: 985 candidates over 536 problems that passed the strict check.
- The teachers' strict-kept specifications: DeepSeek v3.2 on Bedrock and the primed 9B, 468 over 255 problems
  (`out/v10/teacher-strict-kept.jsonl`), plus the 9B chunks written after 2026-10-22 16:17Z once
  `t/recipes/v9_strict_specs.py` has checked them.
- The repair traces: 232 from the student's own dropped candidates and 293 from the teachers'.
- **The Cohere teacher (new, written permission 2026-10-24).** `command-a-reasoning-08-2025` and
  `command-a-plus-05-2026` piloted head to head on the same 50 failed training problems with the DeepSeek lane's
  prompt. Strict-kept specifications per dollar decides the model; it then runs the remaining failed problems
  in size order. Every call is priced in the grant ledger (`~/.config/cohere/ledger.jsonl`, hard stop at $950).
  Every Cohere-written row is labelled by source and the data card cites the permission
  (`internal/COHERE-GRANT-UPDATES.md`). Cost basis for the pilot: the DeepSeek lane used about 37,000 prompt and
  3,200 reply tokens per problem; at Command A's listed $2.50 and $10 per million that is about $0.13 a problem
  before reasoning tokens, so roughly $15 to $30 for the pilot. The ledger records the real figure.

**Which candidate has what.** Candidate A (registered and training since 2026-10-24,
`t/PREDICT-2026-10-24-release-6.1-candidate-a.md`, 6,727 rows) has the base, v9's and the earlier teachers'
strictly kept specifications and the repair traces. Candidate B adds the Cohere teacher's rows and the 9B chunks
written after 16:17Z on 10/22, once the strict check has passed them; it is the 6.2.0 candidate.

**Recipe.** v5's, unchanged: Qwen/Qwen3.5-4B at 851bf6e8, QLoRA NF4, rank 64, alpha 16, dropout 0.1, lr 2e-4,
5 epochs, max-len 2845, batch 1, grad-accum 16, `t/student_sft.py` at its pinned digest, seeds 1 and 2.

## 5. Where work runs (the user, 2026-10-24: "outsource for this stuff always. we use the laptop to test if something doesnt work")

- **The laptop is for tests:** a quick check when something does not work, and the release's own laptop condition
  (does dawnr run smoothly on this laptop). Decoding candidates, seven-kernel grading, the ceiling and spec-33
  readings, strict checks, teacher lanes and full test suites run elsewhere.
- **GitHub's CI runs the test suites** on every push (read `gh run list`), and its install-smoke workflow checks a
  published release on fresh Ubuntu and macOS machines.
- **Cohere's API writes; the desktop runs the lane around it,** on cores 12 to 23 so training keeps its own
  (`t/recipes/teacher_cohere_full.sh` with CPUS=12-23 in the clone `~/dawnr-lane`).
- **The desktop trains** the candidates on its RTX 4080 at 150 W, and, when no cloud machine is available, decodes and
  grades them after training (its 14 GB cannot hold a seven-kernel grade beside a training run).
- **Cloud machines on credit** (the AWS credit for CPU grading, Google Cloud's trial for GPU decoding) take decoding
  and grading as soon as their logins are renewed; both had expired on 2026-10-24.
- **Large files without the cable** go through a private GitHub repository used only for transfers. With the cable
  plugged in, Tailscale uses it directly.

### The Cohere lane, measured (2026-10-24)

The same 50 failed training problems, ten candidates each, kept by the route and then by the strict check:

| model | problems kept by the strict check | candidates kept | ledger cost | replies cut off |
|---|---:|---:|---:|---:|
| Command A Reasoning (thinking 2,048) | 9 | 18 | $33.83 | 113 of 500 |
| Command A+ (thinking 2,048) | 6 | 11 | $31.96 | 24 of 500 |

Command A Reasoning and Command A+ are limited to 20 requests a minute and 1,000 calls a month even on a production
key (docs.cohere.com/docs/rate-limits), so the full run (about 17,000 calls) uses Command A (500 requests a minute,
no monthly cap); its own pilot on the same 50 problems decides the setting. A higher limit for the reasoning model
can be asked of Cohere Labs.

## 5b. Releases so far and the next increments

- **6.0.0, published 2026-10-24 21:15Z** (tag `v6.0.0` at `b03f6ce5`): the October 5 model under version names, versioned
  installs, the `dawnr do` context fix the laptop check found, the correction of section 2. Laptop check with all seven
  provers: every README command works; `ask` 129 s cold is the slow one (`release/evidence/laptop-6.0.0-2026-10-24.json`).
  GitHub's install-smoke run 40133457459 installs it on fresh Ubuntu and macOS.
- **6.0.1 (app):** the launcher adds the person's tool folders to PATH (from a bare PATH Lean and Verus could not start,
  so two provers read as undecided); `ask` made faster where a stage profile shows the time goes (two provers at a time
  against four saved 9 s of about 100 and cost 4 GB, so prover parallelism is not the lever).
- **6.1.0 (model):** candidate A, if it passes the door.
- **6.2.0 (model):** candidate B, A's rows plus the Cohere teacher's strictly kept specifications.

## 6. Where things stand (carried from the deleted log, paused by the user 2026-10-23 04:52Z)

Nothing below restarts until the user says so.

- **Desktop:** `dawnr-v9s2-train.service` stopped at step 1008 of 1535 (checkpoints 900 and 1000 kept) and was
  disabled with the finished v5s2, v8 and v9 units. It is not resumed: its comparison was built on the mixed control.
  The out/ backup of 2026-10-23 is at `~/dawnr-out-backup-2026-10-23/` there.
- **Laptop:** the v9 arms driver, two native wider grades (`v9-20261022-wider-off1000` and `-off2000`; no resume,
  about seventy minutes each), the 9B teacher lane (131 kept specifications; those after 16:17Z on 10/22 not yet
  strict-checked) and the tandem waiter were stopped.
- **v9's arms in hand:** dev (7 clean, 2 all-seven on one decode), seedoff1000, seedoff2000, wider-off0. Ceiling
  read 2026-10-23: gate precision 0.682; a reference-correct specification within five candidates on 25 problems
  (v5 18), within twenty on 31 (v5 29). Receipts `release/evidence/v9-ceiling-2026-10-23.json`,
  `v9-oracle39-2026-10-23.json`.
- **Teachers so far:** DeepSeek v3.2 kept 193 of 906 failed training problems (21%; 9,090 calls, 33.5 M tokens in,
  2.9 M out); the 9B keeps 16 to 20 of 50 short problems and 2 to 3 of 100 long ones. About 1,800 failed problems
  remain, the long tail, which the Cohere lane is for.

## 7. Milestones, each with its DONE WHEN and its Cohere update

| | milestone | DONE WHEN | where |
|---|---|---|---|
| M0 | this plan, the scaffold (`VERSION`, `dawnr version`, the log retired), the public correction of section 2, and the dawnr 6.0.0 release (the October 5 model under version names, versioned installs) | CI green on the commit; the release installs from a clean checkout | laptop |
| M1 | v5's laptop baseline for condition 5; `dev-206.txt` written; optionally v9's two unfinished wider grades | baseline numbers and the panel file on main | laptop |
| M2 | base audit under today's policy; the Cohere pilot and lane; rows built, audited, hashed; the PREDICT file with the five conditions | `t/PREDICT-2026-10-2x-release-6.0.md` on main before any training step | laptop and the Cohere API |
| M3 | seeds 1 and 2 trained, adapters and exports back on the laptop | both exports hashed in the PREDICT file | desktop |
| M4 | six decodes and grades on the 206, the ceiling instrument, the 33 specifications, the laptop bar; the choice; the held-out 182 read once | all five conditions written with receipts | laptop |
| M5 | release engineering: `dawnr-6.0-*.gguf` and `dawnr-6.0.sha256` beside the kept v5 manifest, `release/DATA-dawnr-6.0.json`, the full 6.0 card, README, SCOREBOARD, `docs/MEASURED.md`, `release/ROLLING.md`, CITATION.cff as dawnr 6.0.0, `VERSION` 6.0.0, `SHA256SUMS` and signature, tag `v6.0.0` with the rolling tag moved to it | a clean checkout on a second machine reproduces the card's table with `t/reproduce.sh`; CI green on the tag | laptop |
| M6 | the update to Cohere Labs for the release, and the final report | the entry in `internal/COHERE-GRANT-UPDATES.md` and the user's "sent" | none |

Cohere Labs gets an update at every incremental release (the condition of the permission) and a drafted entry at
every milestone (the user's rule of 2026-10-24).

## 8. Naming and files

- Model files: `dawnr-6.0-0000N-of-0000M.gguf`, `dawnr-6.0.sha256`, `LICENSE-dawnr-6.0`, `NOTICE-dawnr-6.0`. The
  `student` names stay on the v5 files for reproduction and are not reused.
- Documents: `release/MODEL-CARD-dawnr-6.0.md` (a stub until M5), `release/DATA-dawnr-6.0.json`, the 6.0 PREDICT
  file, receipts `release/evidence/6.0-*.json`.
- `VERSION` reads `6.0.0-dev` until M5 sets `6.0.0`; `dawnr version` prints it.
