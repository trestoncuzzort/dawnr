#!/usr/bin/env python3
"""verify_dataset.py — the data-integrity GATE.

Before any training, re-run every preference pair through the verifier in BOTH
directions: `chosen` must still PASS its hidden tests and `rejected` must still
FAIL them. A rejected that passes is preference noise (nobody checked the rejected
side at generation time). Pure local execution — no model, no training env.

COVERS THE FILE TRAINING ACTUALLY LOADS. dpo_pairs_capped.jsonl is what
train_native.py reads; verifying only dpo_pairs.jsonl left that coverage merely
transitive (capped is built as a subset, so it *ought* to inherit the result).
"Ought to" is not a gate, so the capped file is now verified by name. Pairs are
deduplicated by content first, so the subset costs almost no extra subprocesses.

On success this writes a RECEIPT (schema in dataset_gate.py) recording the sha256
of every file it verified. train_native.py refuses to start without one that
matches its inputs — that is what makes "verified before training" a mechanism
rather than a habit.

Also reconciles the known_hard.json vs ledger contradiction (multiply_strings).

FOUR WAYS THIS GATE USED TO SAY PASS WITHOUT HAVING CHECKED
-----------------------------------------------------------
1. A COLLIDING SIGNATURE. signature() concatenated prompt + chosen + rejected +
   tid with no delimiter and hashed the string. Concatenation is not injective.
   THE DIGEST IS OF THE WHOLE FIXTURE, so the two pairs are given here in full:
   {"prompt": "ab", "chosen": "c", "rejected": "r", "meta": {"tid": "t"}} and
   {"prompt": "a", "chosen": "bc", "rejected": "r", "meta": {"tid": "t"}} both
   concatenate to "abcrt" and both hashed to
   sha1("abcrt") = ca1cf76fb284896905ebd7cc391407f1eae89585, executed both ways.
   Quoting that digest beside the prompt/chosen halves alone does not reproduce
   -- those two fields build "abc", whose sha1 is a9993e36... -- and a citation
   a reader cannot re-run is not a citation.
   Deduplication is what makes that fatal rather than untidy -- load_pairs keeps
   the FIRST pair under a signature and every later row inherits its verdict, so
   the second pair was never executed and was still counted as verified. The
   four fields are now hashed as a canonical JSON object under sha256, where the
   field boundaries survive.
2. A MALFORMED LINE WAS SKIPPED IN SILENCE. `except json.JSONDecodeError:
   continue`. A truncated write, a half-flushed append or a hand-edit made the
   row disappear from the count, and the gate reported PASS over whatever it
   could still parse. A file the gate cannot read is not a file the gate has
   cleared, so an unparseable non-empty line is now a violation carrying its
   filename and 1-based line number. A blank line is still just a blank line.
3. NO PARTITION CHECK. Nothing asserted that a training pair belongs to the
   TRAINING side of the frozen split. "chosen passes, rejected fails" is true of
   a contaminating pair too, so a pair labelled with one of the 31 frozen RULER
   task ids would have been executed, verified and passed -- training on the
   eval set with a receipt to show for it. Every non-seed tid must now be in
   ruler_frozen.json's training_pool, and any tid in the frozen ruler is fatal.
4. A FILE WITH NOTHING IN IT PASSED AFFIRMATIVELY. Every number this gate
   reports is a count OVER the rows it parsed, so a pair file truncated to zero
   length -- or one left holding only blank lines -- scored zero on all of them:
   0 unique pairs, 0 malformed lines, 0 off-partition pairs, 0 violations, exit
   0, "PASS: 0/0 pairs valid". The receipt entry it wrote reads {"pairs": 0,
   "violations": 0}, which is exactly the shape require_verified() grants
   permission on, and the trainer was told "verified receipt OK --
   dpo_pairs.jsonl (0 pairs); 0 violations, hashes match". "Nothing was checked"
   and "everything checked out" are different answers and this gate has to tell
   them apart, so a pair file that is PRESENT with zero parseable rows is now a
   violation in its own right (no_verifiable_rows).

AND A FIFTH, WHICH IS WHY THE OTHER FOUR NOW REACH THE TRAINER
--------------------------------------------------------------
Each of the four changed what THIS FILE calls a violation, and nothing in the
receipt said which version of this file wrote it: the verifier fingerprint
covered forge.py, the task source and the interpreter. A receipt issued before
them therefore went on matching perfectly afterwards, and require_verified()
granted permission on a "0 violations" computed by a gate that had never asked
any of the four questions. The same silence covered the frozen split that check
3 reads at verification time: re-freeze the ruler so a training-pool task
becomes an eval task, and the old receipt still accepted, so a pair labelled
with it could be trained on under a receipt that never checked it against that
split. Both files are now in dataset_gate.verifier_fingerprint(), so editing
this one or data/ruler_frozen.json makes every outstanding receipt stop matching
and the gate says which entry moved instead of carrying on. That regenerates
nothing: re-verifying is the maintainer's explicit decision
(docs/UBUNTU-BOOTSTRAP.md, step 6).

NONE OF THE FOUR CHANGES THE VERDICT ON THE RETAINED BYTES, checked before the
change: the committed pair files contain no malformed line, no tid outside the
training pool, no frozen-ruler tid, none of the three is empty (1244 / 918 / 38
parseable rows), and they deduplicate to the same 1279 unique pairs under both
the old and the new signature. These are fences against the next generation run,
not a re-verdict on this one.

AND A SIXTH: THE RECEIPT WAS FINGERPRINTED AFTER THE VERDICT, NOT BEFORE
------------------------------------------------------------------------
The fifth fix put the gate's own bytes and the frozen split into the
fingerprint, which makes a receipt say WHICH questions it answered -- but
the fingerprint was taken at the END of the run, while the split is read at
the START (load_partition, before any pair is executed) and every pair file
is read before that. Verification takes minutes of subprocesses. Change
data/ruler_frozen.json inside that window and the receipt records the NEW
hash beside a verdict computed against the OLD split; re-freeze so a
training task becomes an eval task and the receipt says '0 violations' while
naming the very bytes under which that pair is a violation. Append to a
pair file and the receipt names a sha256 covering a pair nothing executed.
Every input is now hashed BEFORE the checks, re-hashed before the write,
and a difference aborts without writing anything: a receipt whose bytes did
not produce its verdict is the one failure a receipt exists to prevent. On
an undisturbed run the two snapshots are equal and nothing about the
receipt changes -- this is a fence, not a re-verdict.

Writes data/dataset_verification.json. Exit code 1 if any violation is
found, or if an input moved while the verification ran.
"""
from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import dataset_gate
import forge
# task_bank.as_task, not screen_tasks.as_task: this file is published (see
# sync_public.DPO_PUBLISH), and screen_tasks.py cannot be -- it carries the
# private overnight-loop STOP-file path and other references that must never
# leave this machine. task_bank.py is the extracted, publishable piece that
# holds the one function this module actually needs (codex review fold).
import task_bank

DATA = forge.OUT_DIR
# dpo_pairs_capped.jsonl is the run-1 training input (build_training_set.py).
FILES = {"dpo_pairs.jsonl": "forge",
         "dpo_pairs_capped.jsonl": "train",
         "repair_pairs.jsonl": "repair"}


def load_tasks() -> dict[str, forge.Task]:
    """Every task a pair in these files could name — seed tasks AND screened ones.

    THE BUG THIS CLOSES (section 91). `TASKS` was `{t.tid: t for t in
    forge.SEED_TASKS}`, so the gate could only verify pairs drawn from the
    hand-written seed tasks. Section 89 measured pair yield on the AceCode
    TRAINING POOL and appended its 10 `ace_oss_*` pairs to dpo_pairs.jsonl, and
    from that commit on the file was UNVERIFIABLE: every one of those pairs came
    back `no_matching_task`, and re-running the gate could not clear it because
    the definitions were never in the lookup. The gate correctly refused the
    `--uncapped` training path, but its remediation line said "re-run
    verify_dataset.py", which reproduced the same 10 violations forever.

    The pool is not an edge case. Section 89's own finding is that pool tasks
    yield 2.46x more pairs per generation than SEED_TASKS, i.e. they are meant to
    become the MAIN source of pairs — a verifier that cannot see them is a hole
    that reopens on the next generation run, not a one-off.

    WHERE THE DEFINITIONS LIVE: data/screen_results.jsonl carries the full task
    payload (tid / entry / prompt / tests) for every screened candidate.
    data/ruler_frozen.json does NOT — it stores hashes plus a `training_pool`
    list of bare tid strings, by design, so it cannot be the source here.

    The harness is built by task_bank.as_task() (moved out of screen_tasks.py in
    a later fold so this published module does not have to import screen_tasks'
    private screening loop to get it) — the same function that built these tasks
    when they were screened and confirmed. Rebuilding it here would be a second
    implementation of the entry-point binding, and two of those agree only with
    each other.
    """
    tasks: dict[str, forge.Task] = {t.tid: t for t in forge.SEED_TASKS}
    seeded = set(tasks)

    payloads: dict[str, dict] = {}
    path = DATA / "screen_results.jsonl"
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                payload = rec.get("task")
                if not payload or "tid" not in payload:
                    continue
                tid = payload["tid"]
                # A tid re-screened with DIFFERENT bytes would make "verified"
                # depend on which row won the loop. Refuse rather than pick.
                prev = payloads.get(tid)
                if prev is not None and prev != payload:
                    raise SystemExit(
                        f"GATE: {path.name}:{i} redefines task {tid} with "
                        f"different bytes than an earlier row. Verification "
                        f"would depend on row order; refusing to guess.")
                payloads[tid] = payload

    for tid, payload in payloads.items():
        # A screened tid shadowing a seed tid would silently swap the tests a
        # pair is judged against. Neither precedence is safe, so neither is taken.
        if tid in seeded:
            raise SystemExit(
                f"GATE: task id {tid} is defined BOTH in forge.SEED_TASKS and "
                f"in {path.name}. One pair, two possible test suites; refusing.")
        tasks[tid] = task_bank.as_task(payload)
    return tasks


TASKS = load_tasks()


def signature(d: dict) -> str:
    """Content identity of a pair. Verification depends on which task's tests
    run, so the tid is part of the identity, not just the three text fields.

    CANONICAL JSON, NOT CONCATENATION. The four fields used to be glued into one
    string and sha1'd, and gluing loses the boundaries: prompt "ab" + chosen "c"
    is the same string as prompt "a" + chosen "bc", so two different pairs got
    one identity and the second inherited the first one's verdict without ever
    being run. json.dumps escapes quotes and backslashes, so a field's own bytes
    cannot forge a boundary; sorted keys make the encoding independent of dict
    order; and only these four keys are read, so unrelated metadata on the row
    cannot change what "the same pair" means.
    """
    tid = (d.get("meta") or {}).get("tid") or ""
    canonical = json.dumps({"prompt": d.get("prompt", ""),
                            "chosen": d.get("chosen", ""),
                            "rejected": d.get("rejected", ""),
                            "tid": tid},
                           sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_pairs():
    """Returns (unique_pairs, rows_by_file, malformed). A pair present in
    several files is verified once; every file that contains it inherits that
    one verdict.

    `malformed` carries one violation-shaped record per unparseable non-empty
    line. It used to be `continue`, which meant a row the gate could not read
    left no trace anywhere in the report and the file was still eligible for a
    PASS. Blank lines are not malformed -- a file ending in a newline is normal,
    and calling that a violation would make the gate cry wolf on every file.
    """
    unique: dict[str, dict] = {}
    rows_by_file: dict[str, list[str]] = {}
    malformed: list[dict] = []
    for fname, src in FILES.items():
        p = DATA / fname
        if not p.exists():
            continue
        sigs: list[str] = []
        for i, line in enumerate(p.open(encoding="utf-8")):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                # `why` is the CLASS, so the violation-type histogram groups;
                # the varying part (which file, which line, which parse error)
                # lives in `detail`, and in the file/line fields beside it.
                malformed.append({"tid": None, "src": src, "row": i,
                                  "file": fname, "line": i + 1, "ok": False,
                                  "why": f"malformed_line: "
                                         f"{e.__class__.__name__}",
                                  "detail": f"{fname}:{i + 1}: {e.msg}"})
                continue
            sig = signature(d)
            sigs.append(sig)
            if sig not in unique:
                d["_src"], d["_row"], d["_file"] = src, i, fname
                unique[sig] = d
        rows_by_file[fname] = sigs
    return unique, rows_by_file, malformed


def empty_file_violations(rows_by_file: dict[str, list[str]]) -> list[dict]:
    """Pair files the gate could read nothing verifiable out of.

    THE HOLE THIS CLOSES. Every other check here counts something ACROSS the
    parsed rows, so a file with no parseable rows scores zero on all of them and
    the absence of findings reads as a finding of absence: 0 pairs, 0 malformed
    lines, 0 off-partition pairs, 0 violations, exit 0. Worse than the printed
    PASS is the receipt entry, {"pairs": 0, "violations": 0} -- the exact shape
    require_verified() grants permission on, so a dataset file truncated by a
    failed write cleared the gate and training started on it.

    A file with nothing in it did not pass; there was nothing in it to pass. So
    a present pair file with zero parseable rows is a violation of its own, and
    the receipt entry it produces is no longer clean.

    SCOPE, because this is a whole-file verdict and those are easy to overstate:
    only files that EXIST are considered, since load_pairs() skips a missing one
    and never puts it in rows_by_file. A missing file is a different failure and
    already has a different answer -- require_verified() refuses it as NOT
    COVERED by the receipt. This class is for the file that is present and says
    nothing.

    A file whose only rows are unparseable lands here TOO, on top of its
    malformed_line violations. Both statements are true of it and they are not
    the same statement: one says which lines could not be read, the other says
    the file as a whole certified nothing.
    """
    return [{"tid": None, "src": FILES.get(fname), "row": None,
             "file": fname, "ok": False, "why": "no_verifiable_rows",
             "detail": f"{fname}: 0 parseable rows; a receipt over this file "
                       f"would certify nothing"}
            for fname, sigs in rows_by_file.items() if not sigs]


def load_partition() -> tuple[set[str], set[str]]:
    """(frozen ruler tids, training-pool tids) from data/ruler_frozen.json.

    The frozen split is the artifact that decides which tasks are EVAL and
    which may be trained on. Read here rather than restated, so widening the
    pool widens the gate for free and the two cannot drift apart.
    """
    spec = json.loads((DATA / "ruler_frozen.json").read_text(encoding="utf-8"))
    return set(spec["ruler"]), set(spec["training_pool"])


def partition_violations(pairs, split=None) -> list[dict]:
    """Pairs whose task is not on the training side of the frozen split.

    `split` is the (ruler, pool) pair from load_partition(), accepted so a
    caller checking pairs one at a time reads the frozen file once instead of
    once per pair. Passing it changes nothing about the rule -- there is still
    one implementation of it, here.

    THE HOLE THIS CLOSES. check() asks whether `chosen` passes and `rejected`
    fails. That is true of a contaminating pair too, so nothing in this gate
    noticed if a pair was labelled with one of the 31 frozen RULER tasks -- the
    eval set. It would have been executed, verified, counted clean, and trained
    on, with a receipt saying the dataset was checked.

    SEED_TASKS are allowed outside the pool: they are hand-written, predate the
    frozen split, and are neither ruler nor pool members. Refusing them would
    reject the pairs the project started from.
    """
    ruler, pool = split if split is not None else load_partition()
    seeded = {t.tid for t in forge.SEED_TASKS}
    out: list[dict] = []
    for pair in pairs:
        tid = (pair.get("meta") or {}).get("tid")
        rec = {"tid": tid, "src": pair.get("_src"), "row": pair.get("_row"),
               "file": pair.get("_file"), "ok": False}
        if tid in ruler:
            out.append(dict(rec, why="ruler_task_in_training_data"))
        elif tid not in seeded and tid not in pool:
            out.append(dict(rec, why="tid_outside_training_pool"))
    return out


def check(pair) -> dict:
    tid = pair.get("meta", {}).get("tid")
    task = TASKS.get(tid)
    if task is None:
        return {"tid": tid, "src": pair["_src"], "row": pair["_row"],
                "ok": False, "why": "no_matching_task"}
    chosen_ok = forge.verify(pair["chosen"], task).ok
    rejected_ok = forge.verify(pair["rejected"], task).ok
    problems = []
    if not chosen_ok:
        problems.append("chosen_does_not_pass")
    if rejected_ok:
        problems.append("rejected_incorrectly_passes")
    return {"tid": tid, "src": pair["_src"], "row": pair["_row"],
            "ok": not problems, "why": ",".join(problems) or "ok"}


def receipt_inputs() -> tuple[dict[str, str], dict[str, str]]:
    """Everything the receipt will NAME, hashed as of right now.

    (verifier fingerprint, sha256 of each pair file that exists). Called
    twice per run -- once before anything is read, once before the write --
    and the two must agree or no receipt is issued.

    The pair files are enumerated from FILES rather than from load_pairs()'s
    result, because the snapshot has to be taken BEFORE load_pairs() runs; a
    file that appears or disappears inside the window then shows up as a key
    that only one of the two snapshots has, which is drift and is reported as
    such.

    WHAT THIS CANNOT SEE, and it is a real gap rather than a rounding of one:
      - The interpreter entry. dataset_gate.interpreter_fingerprint() caches
        its answer for the process, so the second call returns the first
        call's string by construction and a Python swapped mid-run is not
        detectable here. The FILE hashes are re-read from disk every time.
      - The window between this module's import and the first call. TASKS is
        built at import from data/screen_results.jsonl, so a change in those
        milliseconds lands in both snapshots and is invisible. The window
        this closes is the multi-minute one the checks run in.
      - Anything outside FILES and the fingerprint -- known_hard.json, for
        one, which the report reads but no consumer gates on.
    """
    return (dataset_gate.verifier_fingerprint(),
            {n: dataset_gate.sha256_file(DATA / n)
             for n in FILES if (DATA / n).exists()})


_ABSENT = "(absent)"      # a file that only one of the two snapshots has


def input_drift(before: tuple[dict, dict],
                after: tuple[dict, dict]) -> list[str]:
    """One line per input that is not the same file it was at the start."""
    def short(h: str) -> str:
        # _ABSENT is not a truncated hash, so it does not get the ellipsis:
        # "(absent)\u2026" reads as a shortened digest that happens to spell
        # the word, which is the opposite of what happened to the file.
        return h if h == _ABSENT else f"{h[:16]}\u2026"

    out: list[str] = []
    for was, now in zip(before, after):
        for n in sorted(set(was) | set(now)):
            a, b = was.get(n, _ABSENT), now.get(n, _ABSENT)
            if a != b:
                out.append(f"{n}: at start {short(a)} now {short(b)}")
    return out


def main() -> int:
    # HASHED BEFORE ANYTHING IS READ. The receipt written at the end of this
    # function names the bytes it was verified against, and that claim is
    # only true if the bytes did not move while the verification ran.
    started_with = receipt_inputs()
    unique, rows_by_file, malformed = load_pairs()
    empty_files = empty_file_violations(rows_by_file)
    sigs = list(unique)
    total_rows = sum(len(v) for v in rows_by_file.values())
    print(f"re-verifying {len(sigs)} unique pairs bidirectionally "
          f"(chosen passes / rejected fails) "
          f"covering {total_rows} parseable rows across "
          f"{len(rows_by_file)} files...")
    if malformed:
        print(f"  !! {len(malformed)} line(s) could not be parsed and are "
              f"counted as violations, not skipped")
    if empty_files:
        print(f"  !! {len(empty_files)} file(s) hold no parseable row at all; "
              f"a receipt over them would certify nothing")

    # The frozen split, checked BEFORE anything is executed: a pair drawn from
    # the eval set is a violation whichever way its tests come out. Tracked by
    # signature as well, so a shared pair counts against every file holding it.
    split = load_partition()
    partition: list[dict] = []
    bad_partition_sigs: set[str] = set()
    for s in sigs:
        vs = partition_violations([unique[s]], split)
        if vs:
            partition.extend(vs)
            bad_partition_sigs.add(s)
    if partition:
        print(f"  !! {len(partition)} pair(s) are not on the training side of "
              f"the frozen split")

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(check, (unique[s] for s in sigs)))
    by_sig = dict(zip(sigs, results))

    violations = ([r for r in results if not r["ok"]]
                  + malformed + partition + empty_files)
    by_tid = {}
    for r in results:
        by_tid.setdefault(r["tid"], {"n": 0, "bad": 0})
        by_tid[r["tid"]]["n"] += 1
        if not r["ok"]:
            by_tid[r["tid"]]["bad"] += 1

    # Per-file rollup: a file is clean only if every row in it is clean. A
    # malformed line counts against the file it was read from; an off-partition
    # pair counts against every file that carries it, exactly as an execution
    # violation does. Otherwise a file could hold an unreadable or
    # contaminating row and still report zero.
    #
    # THIS ROLLUP IS THE RECEIPT, not a summary of it: require_verified() reads
    # `violations` per file and grants permission on 0. An empty file therefore
    # has to be counted HERE and not only in the printed report, or the gate
    # would name the defect on stdout and still certify the file.
    malformed_by_file: dict[str, int] = {}
    for v in malformed:
        malformed_by_file[v["file"]] = malformed_by_file.get(v["file"], 0) + 1
    empty_by_file = {v["file"] for v in empty_files}
    per_file = {
        fname: {
            "pairs": len(sl),
            "violations": (sum(1 for s in sl if not by_sig[s]["ok"]
                               or s in bad_partition_sigs)
                           + malformed_by_file.get(fname, 0)
                           + (1 if fname in empty_by_file else 0)),
        }
        for fname, sl in rows_by_file.items()
    }

    # Reconcile known_hard vs ledger.
    kh = []
    khp = DATA / "known_hard.json"
    if khp.exists():
        kh = json.loads(khp.read_text())
    reconcile = {tid: {"pairs_in_dataset": by_tid.get(tid, {}).get("n", 0),
                       "labeled_known_hard": tid in kh} for tid in set(list(by_tid) + kh)}
    contradictions = {t: v for t, v in reconcile.items()
                      if v["labeled_known_hard"] and v["pairs_in_dataset"] > 0}

    # THE RECEIPT MUST NAME THE BYTES THAT PRODUCED THE VERDICT. Everything
    # above ran against the files as they were at started_with; if any of
    # them has moved since, the report below would carry the new hashes
    # beside the old run's answers -- a receipt vouching for bytes it never
    # checked, which is precisely what a receipt is for. Nothing is written.
    drifted = input_drift(started_with, receipt_inputs())
    if drifted:
        raise SystemExit(
            "GATE: an input to this verification CHANGED while it ran.\n"
            + "".join(f"  - {d}\n" for d in drifted)
            + "  The verdict above was computed against the bytes as they\n"
            "  stood at the start, so a receipt written now would name bytes\n"
            "  that did not produce it. No receipt written.\n"
            "  Re-run:  python verify_dataset.py")

    report = {
        # schema/files are the RECEIPT train_native.py checks; the rest is the
        # human report. One artifact, one truth about the same verification run.
        "schema": dataset_gate.SCHEMA,
        "total_pairs": len(sigs),              # unique pairs actually verified
        "total_rows_across_files": total_rows,  # rows, counting shared pairs once per file
        "violations": len(violations),
        # The three counts that add up to it, so a reader can see WHICH gate
        # failed rather than only that one did.
        "violations_by_class": {
            "execution": sum(1 for r in results if not r["ok"]),
            "malformed_lines": len(malformed),
            "off_partition_pairs": len(partition),
            "no_verifiable_rows": len(empty_files),
        },
        "violation_detail": violations[:50],
        "per_tid": by_tid,
        "files": dataset_gate.build_file_entries(DATA, per_file),
        # What "verified" meant when these numbers were produced -- the
        # snapshot taken BEFORE the checks, not a re-read after them. The
        # guard above has just established that the two are the same.
        "verifier": started_with[0],
        "known_hard": kh,
        "reconcile_contradictions": contradictions,
    }
    dataset_gate.receipt_path(DATA).write_text(json.dumps(report, indent=2))

    for fname, e in report["files"].items():
        print(f"  {fname:<24} {e['pairs']:>5} rows  "
              f"{e['violations']} violations  sha256 {e['sha256'][:12]}…")
    # A malformed line is not a pair, so it cannot be subtracted from the pair
    # count; and a pair can fail execution AND the partition check, so the bad
    # ones are counted as a set rather than summed.
    bad_sigs = {s for s in sigs if not by_sig[s]["ok"]} | bad_partition_sigs
    print(f"\n{'PASS' if not violations else 'FAIL'}: "
          f"{len(sigs) - len(bad_sigs)}/{len(sigs)} pairs valid"
          + (f"; {len(malformed)} unparseable line(s)" if malformed else ""))
    if violations:
        from collections import Counter
        print("  violation types:", dict(Counter(v["why"] for v in violations)))
        for v in violations[:10]:
            print(f"    {v['src']}[{v['row']}] tid={v['tid']}: {v['why']}"
                  + (f"  ({v['detail']})" if v.get("detail") else ""))
    if contradictions:
        print("\nRECONCILE: tasks labeled known_hard BUT present as training pairs "
              "(label is stale — they were solved):")
        for t, v in contradictions.items():
            print(f"    {t}: {v['pairs_in_dataset']} pairs in dataset, known_hard={v['labeled_known_hard']}")
    print(f"\nwrote {dataset_gate.receipt_path(DATA)}")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
