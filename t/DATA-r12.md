# The data r12 trains on: the queue, the torn records, the dev split

Written 2026-09-25 for section B of `t/RUN-NEXT-locallm-r12.md`. Everything below was
read from the lab workstation's `t/out` or produced by `t/r12_data_queue.sh` on the day;
the counts name the command that produced them. No home paths, hosts or addresses: the
lab is `T_LAB` in the gitignored `t/lab-workstation.conf`.

## 1. What exists, and what the queue does with it

| answer set | raw | tasks | pass | table today | what the queue does |
|---|---:|---:|---:|---|---|
| `qwen235-train` (pool v5) | 2,767 | 499 | 401 | none in the tag; the RAM-disk grade of 2026-09-21 has 247 rows, 56 clean, graded with SPARK `-j8` inside every cell: 94 rows carry a timeout cell, 3 cells read FLAKED | snapshot the RAM-disk table to `t/out/r12-data/trusted/` (it does not survive a reboot); keep a row only when its graded task equals the current one byte for byte and no cell timed out or flaked; grade every other passing answer, 195 of which were never queued |
| `qwen235-train-p4` (pool v5) | 2,766 | 662 | 483 | none | extracted and tested 2026-09-25 (`p4-extract`, below); grade the passing answers whose program no `qwen235-train` row already graded (same canonical key), copy the row otherwise |
| `qwen235-v6new` (pool v6) | 1,030 | 121 | (never tested as a whole) | 121 rows, 52 clean | 15 raw records are torn (section 3): the fresh tag `qwen235-v6new-r12` was built 2026-09-25 from the leading record of each, extracted and tested under pool v6 (149 tasks, 72 pass); the 121 old rows are kept only by content and without timeouts |
| `qwen235-v6new-p4` (pool v6) | 1,030 | 213 | 86 | 213 rows, 45 clean among the passing | spec check under pool v6, then the split-v6 build |
| `prover-train2` (pool v5) | 450 | 75 | 37 | only the reversed session's table, untrusted | all 37 passing answers regraded with `--no-cache` |
| `qwen2.5-coder-1.5b-r0hf`, `-r0hf-v3`, `-r1-samp-s1`, `qwen3.8-27b-fp8-np1024` | | | | complete tables, never spec-checked | spec check under pool v5 |

Every grade the queue runs passes `T_LAB_RUN_PAR=--no-cache`. `run_par.py` caches
UNPROVED, and every cache entry these programs could hit came from tables graded at load
78 to 351 on 120 cores with SPARK `-j8` inside each cell; a load-induced UNPROVED would be
kept for good. The saving the cache would have given comes from the queue's own dedupe: a
program already graded by a trusted row (same `pool_pick.key`: name, format version and
gate erased) is not graded again, its row is copied.

## 2. Running it

    bash t/r12_data_queue.sh status          # sentinels, the tags, the lab's admission decision
    bash t/r12_data_queue.sh p4-extract      # done 2026-09-25
    bash t/r12_data_queue.sh v6new-repair    # done 2026-09-25
    bash t/r12_data_queue.sh train           # snapshot, plan, grade in chunks of 40, merge
    bash t/r12_data_queue.sh p4
    bash t/r12_data_queue.sh prover2
    bash t/r12_data_queue.sh v6new
    bash t/r12_data_queue.sh spec            # each tag under its one pool
    bash t/r12_data_queue.sh build           # sft-r12/pairs-r12 (split-v5) and sft-r12v6 (split-v6)
    bash t/r12_data_queue.sh dev-ids         # done 2026-09-25, t/r12-dev-ids.json
    bash t/r12_data_queue.sh verify-dev t/out/loop/corpus-r12-headed.txt

The queue is a controller: it runs from this checkout, every Python step runs on the lab
over ssh inside its `~/tup`, niced, and grading goes only through `t/grade_lab.sh tags`.
It cannot run on the lab against itself (the lab has no host key for its own address).

**Admission.** Before every step, and again before every grading chunk, the lab's process
table is read (by uid, from `/proc`, never by matching command lines) and the step is
refused while: a process of ours is stopped; a prover of ours has parent pid 1; a pid in
cpu-yield's `frozen.pids` is alive; or the one-minute load is above 70 percent of the
cores. Grading is also refused while a generation process of ours runs, and when the
headroom `floor((0.70 * cores - load) / 4)` is below one cell: `--jobs 0` is not "no
cells" in `run_par.py`, it is every core. The default is to refuse and exit 3;
`R12_WAIT_MINUTES=N` re-checks every five minutes instead. Cells are capped at
`R12_MAX_CELLS` (12). The queue never kills anything.

**Sentinels.** A step is done when `t/out/r12-data/done/<step>.json` on the lab records
the sha256 of the step's outputs. The same digest skips the step; a different one refuses
by name, and an absent output is "not done", never "done with different inputs". A tool's
output existing on disk never counts as completion (that is how a one-row `AGREEMENT.md`
was read as the committed matrix for five days).

**Chunks and tables.** `plan` writes `t/out/r12-data/chunks/r12-<tag>-cNN/grade-in/` on
the lab with a manifest of names and content hashes. Each chunk is fetched here, graded
with `T_LAB_JOBS=<cells> T_LAB_SETS=1 T_LAB_RUN_PAR=--no-cache bash t/grade_lab.sh tags
<chunk>`, and the returned table is validated on its own, whatever grade_lab.sh's status:
rows equal the manifest, exactly the seven kernel columns, no column malformed on 90
percent of rows, timeouts and flakes counted. `merge` installs `<tag>/kernels.md` from the
trusted rows and the chunk rows, keyed by the sha256 of the task each row graded against
the tag's current `tasks/<name>.json` (Bazel's action-cache rule: a result is reused only
for the exact input it came from), backing up any existing table as `kernels.md.pre-r12`.
It refuses when a passing answer has no trustworthy row.

**Spec checks** run last, one pool per tag, with `--out t/out/r12-data/SPEC-CHECK-<tag>.md`.
`spec_check.py` also rewrites the tracked `t/out/spec-disagree.json` at a fixed path on the
lab; the queue says so and prints the rsync that carries it back, because the lab's
`git pull --ff-only` will refuse until that file is committed here.

**Build** runs `loop_dataset.py --from-samples` over the r8 recipe's tag glob plus this
queue's sources against split-v5 (`--out-suffix r12`), and over the two v6 tags against
split-v6 (`--out-suffix r12v6`); `R12_BUILD_TAGS` overrides the v5 list. It refuses when a
listed tag has no table. Then `t/preflight.py --split t/out/loop/split-v5.json --pool
t/out/loop/sft-r12.jsonl --strict` is step 2 of the run.

## 3. The 15 torn `qwen235-v6new` records

Ids: 5737501, 5835422, 6181516, 6372072, 6404313, 6604592, 7167068, 7468807, 7518673,
7694622, 10076656, 10136726, 10410567, 10477076, 10699683 (15 of 1,030; recounted
2026-09-25, all 15 still unparseable).

Every one has the same shape: a complete record, then 3 to 1,895 bytes of the tail of a
second, longer record for the same problem (its closing reply text, `reply_tokens`,
`wall_s`, `done_reason`). The leading record re-serialises byte for byte with
`json.dumps(obj, indent=1)`, has all 14 keys, a `task_id` equal to the file name, prompt
v3, pool v6, temperature 0, seed 1, and `done_reason` "stop".

Cause: two generators wrote the tag at the same time. The generation log shows two
progress streams interleaved from 756/1032 to the end and the final "1030 of 1032" line
printed twice in a row (six times in all, four of them later reruns). `cmd_generate`
wrote each record with `Path.write_text`, which opens with `O_TRUNC` and renames nothing,
so when both processes had opened a file the shorter record landed over the head of the
longer one. The file times fall inside the overlap. Extraction then crashed at 5737501,
the smallest torn id, with a partial `tasks/`, which is why the tag's table has 121 rows:
268 answers above that id were never extracted.

Repair (`v6new-repair`, done 2026-09-25): a fresh tag `qwen235-v6new-r12`. The 1,015
intact files are copied byte for byte; each torn file becomes its leading record's exact
bytes, and only after every check passes: byte-exact round trip, the tag's 14 keys,
`task_id` equal to the file name, options, model, prompt and pool equal to the tag's other
records, `messages` equal to `build_prompt` under pool v6, and a tail that ends a second
record. If any file fails, nothing is written. The original tag is never touched;
`REPAIR.json` in the new tag lists what was copied and what was repaired, with hashes.
The second answer of each torn pair is lost: only its tail survives, no other copy exists
(the desktop's partial copy predates the overlap and holds none of the 15).
`R12_V6NEW_MODE=drop` omits the 15 instead of repairing them.

The code fix, so it cannot recur: `spec_experiment.write_record` writes to a temp file in
`raw/` and `os.replace`s it into place (atomic on one filesystem), `tag_lock` takes an
advisory `flock` on `raw/.generate.lock` so a second generator on the same tag refuses to
start, and `extract_tag` parses every raw file before writing any task, refuses the
extraction by name when one does not parse, and removes task files an earlier extraction
left that this one did not produce. Tests: `t/test_spec_experiment_writes.py`.

## 4. The dev split, `t/r12-dev-ids.json`

For choosing the fine-tune's stopping step by tests passed, without spending a positive.
Candidates are split-v5 `train_ids` below the HumanEval base (MBPP) that are in pool v5
with at least one test point. Excluded:

1. a positive: some tag holds a test-passing answer that is clean in all seven kernels;
2. a pending positive: some tag holds a test-passing answer never graded seven ways;
3. named in training data: the id appears, under any alias `loop_filter.problem_ids_in`
   knows, in any `sft-*`/`pairs-*` file (text or `task_id` field), any corpus, any lifted
   task or any committed task;
4. on the decontamination list (`exclude_future_train_ids` or `overlap_ids`).

The survivors are ordered by `sha256("r12-dev:" + id)` and the first 100 are the dev ids,
so membership depends only on the id and the salt, not on the rest of the pool. The file
records the rule, the salt, the input digests, every count and the full eligible list in
hash order; `t/test_r12_data_queue.py` recomputes the choice from that list.

The earlier draft rule also excluded any problem whose function some passing answer or
corpus document already computes (found by running it on the problem's own points). It
was dropped: it removes the 65 problems whose answers were graded and are not clean, which
can never become positives, and it may leave fewer than 100 problems. The corpus builder
and preflight are to refuse dev ids under every alias (callers, section 6), which is what
keeps a later relabeling from training on one.

Counts from the run of 2026-09-25 (`dev-ids`, after `p4-extract` and `v6new-repair`):
417 MBPP train ids, all with tests; 73 positives; 216 pending (most of them the 483
passing p4 answers not yet graded; grading moves them to positives or to graded-not-clean,
and neither changes the eligible set, which excludes pending ids already); 99 named in
training data; 17 on the decontamination list; **174 eligible**, of which the first 100 in
hash order are the dev ids (the exclusions overlap, so the numbers do not add up to 417).

The limit, stated: problems no model has solved are harder than the held-out set, where
locallm passes 0 of 200 today, so the stopping-step selector should also count assertions
passed and keep the default step when every checkpoint reads 0.

## 5. `t/grade_lab.sh`, what changed and what still bites

Fixed 2026-09-25:
- `par` (behind `tags` and `pending`) returns non-zero when any set fails. It ended in a
  bare `wait`, whose return status is zero whatever the jobs did, and its throttle's
  `wait -n || wait` reaped a failure without recording it.
- `grade` removes a stale `$WORK/<tag>/kernels.md` before `run_par` starts and copies a
  table back only when `run_par` exited 0 and wrote it; before, a table from an earlier
  run came back as this run's.
- `heldout` takes the pool from the raw records (one pool per set, or it refuses) instead
  of hard-coding `--pool v3`, which was wrong for every train-side tag.
- every grade first runs `t/stall_check.py` on the lab (`lab_quiet`); until the lab's
  checkout has that file (track T3 of the r12 build), grading is refused by name, not
  started blind.
- `matrix` passes `T_SPARK_JOBS=1` like `grade`, clears the old table first, and refuses
  to copy back after a failed `run_par`.

Still true, and the queue works around them: `grade` returns 0 and does nothing when the
controller's `kernels.md` already exists or `.grading` exists (the queue moves stale tables
aside and refuses on a lock); `--jobs $((JOBS / SETS))` gives 0 cells when `JOBS < SETS`
(the queue passes `T_LAB_SETS=1` and refuses below one cell); the lab's old grade queue
logged `rc=$?` after a `$(date)` substitution, so `GRADED ... rc=0` there was `date`'s
status (the queue writes statuses on their own line).

## 6. What was run on 2026-09-25, and what remains

Run (light, one core, `nice -n 19`, writing only under the lab's `t/out`):
- `p4-extract`: `extract: 2766 replies; parse 1755, task 662, wf 349` then `tests: 662
  tasks; fail 142, pass 483, requires-excluded 6, signature 6, undefined 25`. Sentinel
  `extract-qwen235-train-p4`.
- `v6new-repair`: `{"source": "qwen235-v6new", "mode": "repair", "pool": "v6", "intact": 1015,
  "repaired": [15 ids], "dropped": [], "sha256": 1030}`: every one of the 15 passed every
  check, including `messages` equal to the prompt pool v6 builds. Then, under pool v6,
  `extract: 1030 replies; parse 766, task 149, wf 115` and `tests: 149 tasks; fail 51, pass
  72, requires-excluded 11, signature 3, undefined 12`. The old tag's table had 121 rows;
  the new tag has 149 tasks and 72 passing answers to grade. Sentinels
  `repair-qwen235-v6new`, `extract-qwen235-v6new-r12`.
- `dev-ids`: the counts in section 4; `t/r12-dev-ids.json` (tracked) and
  `t/out/loop/r12-dev-ids.txt` on both machines.

Not run, deliberately: every grading step, every spec check, the build. The lab's cores
are shared, and the committed-matrix regrade of the same day was still the day's grading.

Callers to update, outside this track's files:
- `t/loop_locallm.py cmd_corpus` and `t/preflight.py`: refuse any `t/r12-dev-ids.json` id
  under every alias (`loop_filter.problem_id`); relabeling must never relabel a program
  onto a dev id; run step 4 should call `bash t/r12_data_queue.sh verify-dev <corpus>`.
- `t/loop_dataset.py`: apply `exclude_future_train_ids` when building `sft`/`pairs`, so the
  waiting teacher answers to train ids on that list never enter a pool file (the r12
  plan's A2 names this; the builder drops them only later).
- the stopping-step selector: decode `t/out/loop/r12-dev-ids.txt` greedily at every kept
  checkpoint, score by problems passed with assertions passed as the tie-break, earliest
  step on a tie, default step when every checkpoint reads 0.
- `t/stall_check.py` (track T3): `grade_lab.sh` now calls it on the lab before every grade.
