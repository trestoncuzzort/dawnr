# Research and training takeover

## Taken over, later on 2026-09-19. Read this section first.

The handoff below was accepted and acted on. What it said was outstanding is
now either done or superseded; the original text is kept unedited underneath so
the state it described stays readable.

**The 4000-step source study finished.** Six of six arms, no integrity issue.
`summary-4000.json` and `summary-4000.md` are in the study directory and
[FINDINGS-source-longer-2026-09-19.md](../locallm/FINDINGS-source-longer-2026-09-19.md)
reports it. Two registered predictions held and the third was falsified in the
opposite direction: the modern core is 5.9-7.4% *worse* than its GPT control at
every seed, after leading by about a quarter at 1000 updates, and it is also
18.8% slower and 33% heavier in memory. Completions from all six arms were
sampled and are still repetitive; a 45% cut in token loss bought no usable
completion.

**Watcher ownership moved.** The private watcher's Codex wake route had already
failed once (`thread ... already has an active writer`), so its control file is
now `enabled: false` with the reason recorded in it, and the new owner watches
the same probe directly. It idles without polling and without waking anything;
re-enable it only if that delivery route is restored. Only one repair loop is
running.

**The missing dataset and scorer exist, with tests.** New, all tested on the
lab: `t/composition_reference.py` (closed-form oracle that never sees an AST),
`t/build_composition_dataset.py` (whole-pattern holdouts, frozen contracts,
family exclusion manifest, card, 10,800 corruption checks rejected),
`t/score_synthesis.py` (independent scorer: correct, wrong, malformed,
ill-formed, contract-altering, undefined, over-budget, timed-out, over-length),
`locallm/audit_example_masks.py` (tokenized mask audit on the frozen BPE),
`locallm/train_factorial.py` (resumable arm trainer with frozen identities and
core-only inference export), `locallm/sample_candidates.py`,
`locallm/run_factorial_study.py`, `locallm/summarize_factorial.py`. 46 tests
pass on the lab: 22 for the curriculum and scorer, 4 for the mask audit, 6 for
the trainer including a bit-identical resume, 3 for the stop rule, and the 11
inherited research-module tests still pass.

**The factorial is running.** `t/out/factorial-2026-09-19`, twelve arms,
registered in
[PREREG-factorial-2026-09-19.md](../locallm/PREREG-factorial-2026-09-19.md)
before any arm produced a scored output. The design's batch 32 was amended to
batch 8 over 4000 updates -- the same examples per arm -- after a batch-32 arm
was killed by the other user's growing allocation on a card that had measured
17 GiB free seconds earlier; the amendment and its measurements are in the
preregistration, and every arm uses it.

Still outstanding: the factorial's result, and then the seven-verifier, twin and
specification evaluation, which no generated-task score replaces. The dataset is
int-scalar only: no seq, pair or string family yet.


This note supersedes older statements that the first source study is running.
Read AGENTS.md and the original handoff for project constraints.

## Operator stop and ownership transfer

The operator explicitly requested stopping work and leaving this handoff for
other agents. No dataset implementation was written during the interrupted
turn: only the existing design, trace generator, reference oracle and curation
instructions were read. The compositional dataset and scorer remain missing.
No new training run was launched, no running training was stopped, and no
GitHub push was made during handoff preparation. The main handoff and overnight
notes now identify the longer 4000-step study correctly.

The live observation below is the last check, not a fresh check at transfer.
The existing external watcher has not been disabled or redirected. Its next
owner must account for its Codex delivery route before taking over repairs.
This conversation's research goal is being paused at the operator's request;
that does not stop external training or the watcher.

## Verified state

The latest live integrity probe found the longer study running, four of six
arms complete, modern-seed42 at 3000/4000 updates, and no integrity issues.
This is an observation, not a guarantee of its state when this note is read.
Output: `t/out/source-pretraining-longer-2026-09-19` on the lab.
Runner PID 2924784, start ticks 163484467. Recheck with:

```bash
source t/lab-workstation.conf
ssh "$T_LAB" 'cd ~/tup && python3 locallm/probe_pretraining_study.py --out t/out/source-pretraining-longer-2026-09-19 --runner-pid 2924784 --runner-start-ticks 163484467 --integrity'
```

Do not restart a healthy run to add the new methods. Keep core, data, trainer
and study-runner sources frozen. On completion summarize with `--steps 4000`,
inspect all paired seeds and completions, and retain failed attempts. Push
tested updates only after the run ends, as requested by the operator.

The completed 1000-step study improved held-out loss by 24–29%, but sampled
completions were still poor. See the source-pretraining findings. No new
research intervention has demonstrated a quality improvement yet.

## Next experiment

Read `internal/RESEARCH-ANGLES-2026-09-19.md` and
`locallm/DESIGN-latent-execution-2026-09-19.md` before more literature searches.
The strongest candidates combine NextLat token-conditioned latent prediction
with independently checked execution supervision, motivated by ExeDec and
trace-training work. Test baseline, latent, execution, and combined arms using
matched data and seeds. A combined gain and a positive interaction are distinct
claims. The design is not yet launch-ready.

Implemented but uncommitted: NextLat objective, optional research-model wrapper,
completion masks, separate execution loss, interpreter traces, and independent
reference checks. Their tests passed on the lab. The 735-example trace pilot is
development-only; it is not a held-out benchmark or seven-system proof evidence.

Still required: compositional dataset with whole-pattern holdouts and immutable
contracts; independent synthesis scorer; actual corpus token/mask audit;
resumable experiment trainer and identity records; GPU calibration; final
preregistration. Do not launch on the pilot or infer generation gains from trace
accuracy. Project acceptance still requires original tests and all seven proof
systems with broken twins refuted.

## Monitoring and ownership

The lightweight watcher lives in private local state under
`~/.local/state/tup-overnight/`. Its control and heartbeat files identify the
current generation. It polls every 30 seconds and audits integrity every 200.
It currently queues events to this Codex conversation. Another agent must
explicitly take over delivery and repair ownership before relying on it; do not
run two competing repair loops. Do not publish endpoint or thread identifiers.
The active research goal can trigger additional model turns independently of
this watcher; changing agents does not itself disable that goal.

Preserve inherited unverified changes to cache, lifter, lowerings, preflight,
parallel runner and recheck artifacts. Do not claim these were validated by
the new research-module tests. Research PDFs and generated data are ignored;
the research report records their archive locations and provenance.
