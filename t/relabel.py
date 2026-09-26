#!/usr/bin/env python3
"""t/relabel.py -- relabel verified-but-wrong programs with the train problem they actually solve (2026-09-25).

    python3 t/relabel.py --split t/out/loop/split-v5.json --out t/out/loop/relabel-2026-09-25.jsonl \\
        [--root t/out/spec-experiment] [--tags TAG ...] [--n 100] [--seed 1] \\
        [--report t/RELABEL-2026-09-25.md] [--duplicates t/out/loop/relabel-duplicates-2026-09-25.jsonl]

The population this reads is the one `score_heldout.py` calls "wrong but proven": a
row of an answer set's kernels.md that reads `verified / refuted` in all seven columns
while tests.json says the task fails its own problem's tests. All seven proof systems
agreed the program meets the specification the model wrote, the sabotaged twin was
caught, and the problem's tests still failed: a correct implementation of the wrong
function. On 2026-09-21 34-57 percent of them were training programs recited for the
wrong problem (internal/research/r12-2026-09-21/data-growth-lit.md).

CodeIt (Butt et al., ICML 2024, https://arxiv.org/html/2402.04858, research receipt
ee715aca6339; code https://github.com/Qualcomm-AI-research/codeit) keeps such programs
instead of discarding them: a sampled program that does not solve its task is stored
with the task it DID solve (hindsight relabeling), and a 220M model trained that way
reached 49/400 ARC evaluation tasks where sample-and-filter reached 24/400 and
"stagnates". Their relabel target is synthetic (whatever the program output); here it
has to be an EXISTING train problem, because the step locallm fails is English to
specification and a synthetic goal has no English. So for every distinct program:

  1. every TRAIN problem of the split's pool whose signature kinds match is a
     candidate; a held-out id, an id on the same-task exclusion list
     (t/decontamination-2026-09-21.json) or a dev-split id (t/r12-dev-ids.json) is
     never a candidate, and one that reaches the admission step is refused by name;
  2. the program, renamed to the candidate, is run on the candidate's own points
     through the interpreter the tests stage uses (spec_experiment.run_point);
     every point must pass;
  3. its specification must agree with the candidate's reference solution on --n
     random draws shaped like EACH of the candidate's stated examples in turn
     (spec_check.check_task, status "agrees" with draws > 0 for every shape) and hold
     at the stated examples themselves (spec_check.check_points);
  4. it is admitted for the candidate only when EXACTLY ONE candidate qualifies. Two
     qualifying candidates mean two problem statements solved by one program with one
     specification, which is a semantic duplicate pair (Soft Contamination,
     https://arxiv.org/html/2602.12413v1, receipt d826e08043c0: finetuning on semantic
     duplicates moved scores as much as exact duplicates did); the pair goes to the
     --duplicates file for the decontamination track and nothing is admitted.

Programs are deduplicated by loop_filter.key (name, gate and version erased) before any
of this, so an attractor recited by fifteen arms is tested once and its provenance
records every copy. The random draws are seeded per (program, candidate) from --seed and
the renamed program's sha256, which makes each verdict independent of the order the
programs are visited in; spec_check.py threads one generator through every task on
purpose (its verdicts are cited reports) and says this per-task seeding is the safe
route for a new instrument.

Output rows are in the pool-file shape t/loop_dataset.py writes (task_id, task, prompt,
chosen, source) with source "relabel" and a "relabel" provenance block: the answer set
the program came from, the problem it was written for, the program's sha256 there, the
number of copies, the candidates tried, the points and draws that admitted it, and the
pool and seed. The source problem is recorded as an integer and a sha256, never as the
task's alias: preflight refuses a pool file that names a held-out alias anywhere in it,
and that rule stands. loop_dataset.py --relabel-rows appends these rows to the positives
with their source kept, so a later builder can weight real positives higher: CodeIt
without that priority fell from 49/400 to 38/400 (Table 2, A3).
"""

from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import json
import random
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fuzz_lower                                               # noqa: E402
import harness                                                  # noqa: E402
import loop_filter                                              # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

CLEAN = "verified / refuted"
KERNELS = tuple(spec_check.KERNELS)
# the verdicts score_heldout.py counts as "fails its own problem's tests"
FAILING_TESTS = frozenset({"fail", "signature", "requires-excluded", "undefined"})
SOURCE = "relabel"
QUALIFIES = "qualifies"


def fence(text: str) -> str:
    return "```t\n" + text.rstrip() + "\n```"


def task_prefix(tid: int) -> str:
    """The id family a task name carries, exactly as spec_experiment's extract writes it."""
    tid = int(tid)
    return (f"apps_{tid - se.APPS_BASE}" if tid >= se.APPS_BASE else
            f"he_{tid - se.HUMANEVAL_BASE}" if tid >= se.HUMANEVAL_BASE else f"mbpp_{tid}")


def target_name(tid: int, entry: dict) -> str:
    name = f"{task_prefix(tid)}__{entry['fn']}"
    return name if fuzz_lower.NAME_RE.match(name) else task_prefix(tid)


def task_signature(task: dict) -> tuple[tuple[str, ...], str]:
    """The parameter types and the return type a program declares."""
    return (tuple(p["type"] for p in task["params"]), task["returns"][0]["type"])


def problem_signature(entry: dict) -> tuple[tuple[str, ...], str] | None:
    """The kinds a problem's first assertion passes and expects, as t parameter types.

    A seq-of-seq argument is still a t `seq` parameter (run_point accepts it wherever the
    task declares seq), so it is folded into seq on both sides.
    """
    points = entry.get("points") or []
    if not points:
        return None
    first = points[0]

    def fold(kind: str) -> str:
        return "seq" if kind == "seq-of-seq" else kind

    return (tuple(fold(kind) for kind, _value in first["args"]), fold(first["expected"][0]))


# ------------------------------------------------------------------ gates --

@dataclass(frozen=True)
class Gates:
    """The ids no relabel may target, each with the name it is refused under."""

    held_out: frozenset[int]
    listed: frozenset[int]
    dev: frozenset[int]

    def forbids(self, tid: int) -> str | None:
        if tid in self.held_out:
            return "held-out"
        if tid in self.listed:
            return "listed (same-task exclusion)"
        if tid in self.dev:
            return "dev-split"
        return None


def load_gates(split: dict, split_path: Path | str | None) -> Gates:
    eval_ids = frozenset(int(i) for i in split.get("eval_ids", split.get("heldout_task_ids", [])))
    return Gates(held_out=eval_ids,
                 listed=loop_filter.decontamination().exclude_train_ids,
                 dev=loop_filter.r12_dev_ids(split_path=split_path))


def lazy_points(entry: dict) -> list[str]:
    """The lazy programs (spec_check.lazy_functions) that reproduce EVERY point of a problem.

    AlphaVerus's exploit model (arXiv:2412.06176, github.com/cmu-l3/alphaverus), applied
    to the problem's tests instead of a specification: if a constant, the identity, the
    length of the input or its reversal answers every recorded point, the points cannot
    tell a solution from the laziest program and admit nothing. Measured on the first
    run of 2026-09-25: 6 of 44 admitted targets were such problems, 26 of 131 rows, among
    them an APPS problem whose one recorded point is `[3] -> 3` (so `r := n` was admitted
    for "find the nth digit of 1, 2, 3, ...") and one whose one point is `[[], []] -> []`.
    """
    points = entry.get("points") or []
    if not points:
        return []
    hits = []
    for label, lazy in spec_check.lazy_functions():
        for point in points:
            try:
                args = [spec_check.to_t(v) for _k, v in point["args"]]
                guess = lazy(args)
                if guess is None:
                    break
                got = spec_check.to_t(guess) if not isinstance(guess, tuple) else guess
                expected = spec_check.to_t(point["expected"][1])
                if got != expected or isinstance(got, bool) != (point["expected"][0] == "bool"):
                    break
            except (TypeError, KeyError, IndexError, ValueError):
                break
        else:
            hits.append(label)
    return hits


def undiscriminating(pool: dict, ids) -> dict[int, list[str]]:
    """Problems whose recorded points a lazy program reproduces, with the programs that do."""
    found = {}
    for tid in sorted(ids):
        hits = lazy_points(pool[tid])
        if hits:
            found[tid] = hits
    return found


def target_index(pool: dict, train_ids: set[int], gates: Gates,
                 refused=frozenset()) -> dict[tuple, list[int]]:
    """Train problems by signature, never a gated or a refused one, in sorted id order."""
    index: dict[tuple, list[int]] = {}
    for tid in sorted(pool):
        if tid not in train_ids or gates.forbids(tid) or tid in refused:
            continue
        sig = problem_signature(pool[tid])
        if sig is not None:
            index.setdefault(sig, []).append(tid)
    return index


def targets_for(program: dict, index: dict[tuple, list[int]], gates: Gates) -> list[int]:
    """Every candidate for one program. A gated id here is a bug upstream and is refused, not skipped."""
    tids = index.get(task_signature(program["task"]), [])
    for tid in tids:
        why = gates.forbids(tid)
        if why:
            raise SystemExit(f"refusing to relabel {program['tag']}/{program['name']} onto problem {tid}: "
                             f"it is a {why} id and can never be a training target")
    return list(tids)


# --------------------------------------------------------------- reading --

def wrong_but_proven(tag: str, d: Path) -> tuple[list[dict], dict]:
    """The rows of one answer set verified / refuted in all seven while their own tests fail.

    Returns the programs and a summary for the report. A set whose table does not carry
    exactly the seven named kernels contributes nothing and says so; a row whose task
    file is missing is named, never silently dropped.
    """
    cols, cells = se.parse_kernel_table(d / "kernels.md")
    tests_path = d / "tests.json"
    try:
        tests = json.loads(tests_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"{tag}: tests.json is not readable ({error}); a set without test verdicts has no "
                         "wrong-but-proven population, and guessing one is worse than refusing")
    seven = len(cols) == 7 and set(cols) == set(KERNELS)
    info = {"rows": len(cells), "seven_kernels": seven, "wrong_but_proven": 0, "no_task_file": []}
    if not seven:
        return [], info
    by_name: dict[str, tuple[str, str | None]] = {}
    for tid_s, verdict in tests.items():
        if isinstance(verdict, dict) and verdict.get("name"):
            by_name[verdict["name"]] = (str(tid_s), verdict.get("overall"))
    programs = []
    for name in sorted(cells):
        row = cells[name]
        if not all(row.get(k) == CLEAN for k in KERNELS):
            continue
        tid_s, overall = by_name.get(name, ("", None))
        if overall not in FAILING_TESTS:
            continue
        info["wrong_but_proven"] += 1
        path = d / "tasks" / f"{name}.json"
        if not path.exists():
            info["no_task_file"].append(name)
            continue
        task = harness.load(path)
        source_id = int(tid_s) if tid_s.isdigit() else loop_filter.problem_id(name)
        programs.append({"tag": tag, "name": name, "task": task, "source_id": source_id, "tests": overall})
    return programs, info


def distinct_programs(programs: list[dict]) -> list[dict]:
    """One entry per program with the name erased, first copy in (tag, name) order."""
    seen: dict[str, dict] = {}
    for p in programs:
        k = loop_filter.key(p["task"])
        entry = seen.get(k)
        if entry is None:
            seen[k] = entry = {**p, "key": k, "copies": []}
        entry["copies"].append((p["tag"], p["name"]))
    return list(seen.values())


# ---------------------------------------------------------------- checks --

def qualify(task: dict, entry: dict, tid: int, n: int, seed: int) -> dict:
    """One program against one candidate problem: its points, its reference on n draws, its stated examples."""
    name = target_name(tid, entry)
    renamed = se.rename_task(copy.deepcopy(task), name)
    verdicts = [se.run_point(renamed, p) for p in entry.get("points", [])]
    kinds = [v["verdict"] for v in verdicts]
    out = {"task_id": tid, "name": name, "points": len(kinds), "points_passed": sum(k == "pass" for k in kinds)}
    if not kinds:
        out["status"] = "no-points"
        return out
    if any(k in ("arity", "type") for k in kinds):
        out["status"] = "signature"
        return out
    if any(k != "pass" for k in kinds):
        out["status"] = "tests-fail"
        return out
    sha = spec_check.task_sha256(renamed)
    # check_task draws arguments shaped like the problem's FIRST example, on purpose (an
    # example carries unstated preconditions). For a relabel that is too narrow: the
    # second run of 2026-09-25 admitted eight copies of a lookup table,
    # `r := n == 1 or n == 3 or n == 5 or n == 7 or n == 8`, for "is n a happy number"
    # (points 1 -> true, 7 -> true, 16 -> false), because the first example is 1 and every
    # draw then lies in 0..2, where the table happens to be right. So every stated example
    # drives --n draws in turn (the points rotated so each is first), and the reference
    # must agree on all of them; the draws around 7 and 16 reach 10, 13 and 19, where the
    # table is wrong. The instrument is unchanged, only the shapes it is handed.
    points = entry.get("points") or []
    total, weak = 0, False
    for shape in range(len(points)):
        rotated = {**entry, "points": points[shape:] + points[:shape]}
        rnd = random.Random(f"{seed}:{sha}:{tid}:{shape}")
        result = spec_check.check_task(renamed, rotated, n, rnd)
        status = result.get("status")
        if status != "agrees":
            out["status"] = f"spec-{status}"
            out["shape"] = shape
            return out
        if type(result.get("draws")) is not int or result["draws"] <= 0:
            out["status"] = "spec-no-valid-draws"
            out["shape"] = shape
            return out
        total += result["draws"]
        weak = weak or bool(result.get("weak"))
    examples = spec_check.check_points(renamed, entry)
    if type(examples.get("points_failed")) is int and examples["points_failed"] > 0:
        out["status"] = "spec-contradicts-example"
        return out
    if examples.get("over_constrained") is True:
        out["status"] = "spec-refuses-every-example"
        return out
    out.update(status=QUALIFIES, draws=total, shapes=len(points), task=renamed, task_sha256=sha, weak=weak)
    return out


def relabel_program(program: dict, targets: list[int], pool: dict, n: int, seed: int) -> dict:
    """Try every candidate; the outcome is the row, the duplicate pair, or why nothing qualified."""
    results = [qualify(program["task"], pool[tid], tid, n, seed) for tid in targets]
    tally = Counter(r["status"] for r in results)
    qualifying = [r for r in results if r["status"] == QUALIFIES]
    outcome = {"program": program, "targets_tried": len(targets), "tally": tally, "qualifying": qualifying}
    if len(qualifying) == 1:
        outcome["kind"] = "admitted"
    elif len(qualifying) > 1:
        outcome["kind"] = "ambiguous"
    else:
        outcome["kind"] = "no-target"
    return outcome


def pool_row(outcome: dict, pool: dict, pool_name: str, n: int, seed: int, prompt_version: str) -> dict:
    program, hit = outcome["program"], outcome["qualifying"][0]
    entry = pool[hit["task_id"]]
    tags = sorted({tag for tag, _name in program["copies"]})
    return {
        "task_id": hit["task_id"], "task": hit["name"], "source": SOURCE,
        "prompt": se.build_prompt(entry, prompt_version),
        "chosen": fence(surface.print_task(hit["task"])),
        "relabel": {
            "tag": program["tag"], "from_problem_id": program["source_id"],
            "from_task_sha256": spec_check.task_sha256(program["task"]),
            "from_tests": program["tests"], "copies": len(program["copies"]), "tags": tags,
            "targets_tried": outcome["targets_tried"],
            "targets_passed_tests": sum(v for k, v in outcome["tally"].items()
                                        if k == QUALIFIES or k.startswith("spec-")),
            "points": hit["points"], "draws": hit["draws"], "shapes": hit["shapes"], "weak": hit["weak"],
            "task_sha256": hit["task_sha256"], "pool": pool_name, "n": n, "seed": seed,
        },
    }


def duplicate_row(outcome: dict, pool_name: str) -> dict:
    program = outcome["program"]
    return {
        "kind": "one-program-solves-both", "pool": pool_name,
        "problem_ids": sorted(r["task_id"] for r in outcome["qualifying"]),
        "program_sha256": spec_check.task_sha256(program["task"]),
        "tag": program["tag"], "from_problem_id": program["source_id"],
        "copies": len(program["copies"]),
        "evidence": [{"task_id": r["task_id"], "points": r["points"], "draws": r["draws"]}
                     for r in sorted(outcome["qualifying"], key=lambda r: r["task_id"])],
    }


# ---------------------------------------------------------------- report --

def _shown(path) -> str:
    """A path for the report: relative to the repository, or with the home directory as ~."""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(HERE.parent.resolve()))
    except ValueError:
        return str(p).replace(str(Path.home()), "~")


def write_report(path: Path, args, split_path: Path, pool_name: str, pool_size: int, tags: list[str],
                 per_set: dict, programs: list[dict], distinct: list[dict], outcomes: list[dict],
                 index: dict, gates: Gates, out_path: Path, dup_path: Path,
                 lazy: dict[int, list[str]] | None = None, pool: dict | None = None) -> None:
    lazy = lazy or {}
    pool = pool or {}
    admitted = [o for o in outcomes if o["kind"] == "admitted"]
    ambiguous = [o for o in outcomes if o["kind"] == "ambiguous"]
    no_target = [o for o in outcomes if o["kind"] == "no-target"]
    pair_tally: Counter = Counter()
    for o in outcomes:
        pair_tally.update(o["tally"])
    # per answer set: rows, wrong-but-proven, distinct programs first seen there, admitted copies
    first_seen: Counter = Counter(d["tag"] for d in distinct)
    admitted_copies: Counter = Counter()
    for o in admitted:
        for tag, _name in o["program"]["copies"]:
            admitted_copies[tag] += 1
    ambiguous_copies: Counter = Counter()
    for o in ambiguous:
        for tag, _name in o["program"]["copies"]:
            ambiguous_copies[tag] += 1
    # per target problem
    by_target: dict[int, list[dict]] = {}
    for o in admitted:
        by_target.setdefault(o["qualifying"][0]["task_id"], []).append(o)
    # per signature
    by_sig: dict[tuple, dict] = {}
    for d in distinct:
        sig = task_signature(d["task"])
        g = by_sig.setdefault(sig, {"programs": 0, "copies": 0, "admitted": 0, "ambiguous": 0,
                                    "targets": len(index.get(sig, []))})
        g["programs"] += 1
        g["copies"] += len(d["copies"])
    for o in outcomes:
        sig = task_signature(o["program"]["task"])
        if o["kind"] in ("admitted", "ambiguous"):
            by_sig[sig][o["kind"]] += 1
    # where the admitted programs were written for
    origin: Counter = Counter()
    for o in admitted:
        src = o["program"]["source_id"]
        origin[gates.forbids(src) if src is not None and gates.forbids(src) else
               ("train" if src is not None else "unknown")] += 1

    def sig_text(sig: tuple) -> str:
        return f"({', '.join(sig[0])}) -> {sig[1]}"

    L: list[str] = []
    L.append("# Relabeling verified-but-wrong programs with the problem they solve, 2026-09-25")
    L.append("")
    L.append(f"`python3 t/relabel.py --split {_shown(split_path)} --n {args.n} --seed {args.seed}"
             f" --prompt-version {args.prompt_version}`, run "
             f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%MZ')} over "
             f"{len(tags)} answer sets under {', '.join('`' + _shown(r) + '`' for r in args.root)}, "
             f"pool {pool_name} ({pool_size} problems), "
             f"rows written to `{_shown(out_path)}`, duplicate pairs to `{_shown(dup_path)}`.")
    L.append("")
    L.append("A program is **wrong but proven** when its kernels.md row reads `verified / refuted` in all seven "
             "columns and tests.json says it fails its own problem's tests (the population "
             "`score_heldout.py` counts). Each distinct program (name, gate and version erased, "
             "`loop_filter.key`) is run on every same-signature train problem's points through the tests "
             "stage's interpreter, then its specification is checked against that problem's reference "
             "solution on random draws and at the problem's stated examples. It is admitted for a problem "
             "only when exactly one problem qualifies; held-out, listed and dev ids are never candidates.")
    L.append("")
    L.append("## Totals")
    L.append("")
    L.append("| what | count |")
    L.append("|---|---:|")
    L.append(f"| answer sets read | {len(tags)} |")
    L.append(f"| answer sets without exactly the seven kernels (contribute nothing) | "
             f"{sum(1 for i in per_set.values() if not i['seven_kernels'])} |")
    L.append(f"| wrong-but-proven rows | {sum(i['wrong_but_proven'] for i in per_set.values())} |")
    L.append(f"| rows whose task file is missing (named below) | "
             f"{sum(len(i['no_task_file']) for i in per_set.values())} |")
    L.append(f"| distinct programs | {len(distinct)} |")
    L.append(f"| train candidates (pool, train split, not held-out, listed or dev) | "
             f"{sum(map(len, index.values())) + len(lazy)} |")
    L.append(f"| candidates refused: their own points cannot reject a lazy program | {len(lazy)} |")
    L.append(f"| distinct programs with at least one same-signature candidate | "
             f"{sum(1 for o in outcomes if o['targets_tried'])} |")
    L.append(f"| (program, candidate) pairs tried | {sum(o['targets_tried'] for o in outcomes)} |")
    L.append(f"| pairs that passed every point | "
             f"{sum(v for k, v in pair_tally.items() if k == QUALIFIES or k.startswith('spec-'))} |")
    L.append(f"| pairs that qualified (points, draws and examples) | {pair_tally.get(QUALIFIES, 0)} |")
    L.append(f"| **programs admitted (exactly one target)** | **{len(admitted)}** |")
    L.append(f"| programs with two or more targets (duplicate pairs, not admitted) | {len(ambiguous)} |")
    L.append(f"| programs with no target | {len(no_target)} |")
    L.append(f"| distinct target problems | {len(by_target)} |")
    L.append("")
    L.append("### Why (program, candidate) pairs did not qualify")
    L.append("")
    L.append("| status | pairs |")
    L.append("|---|---:|")
    for status, count in sorted(pair_tally.items(), key=lambda kv: (-kv[1], kv[0])):
        L.append(f"| {status} | {count} |")
    L.append("")
    if lazy:
        L.append("### Train problems that can never be a target: their points cannot reject a lazy program")
        L.append("")
        L.append("AlphaVerus's exploit model (arXiv:2412.06176) applied to the problem's own tests: when a "
                 "constant, the identity, the input's length or its reversal answers every recorded point, "
                 "the points cannot tell a solution from the laziest program, so no relabel onto that problem "
                 "is evidence of anything. The first run of 2026-09-25 admitted 26 of its 131 rows onto 6 such "
                 "problems before this refusal existed, among them `r := n` for \"find the nth digit of "
                 "1, 2, 3, ...\" whose one recorded point is `[3] -> 3`; the reference check did not catch it "
                 "because the draws copy the example's shape (0 to 6, where the nth digit is n).")
        L.append("")
        L.append("This also refuses problems whose function IS the lazy program (the larger of two numbers, "
                 "x + 1): a correct relabel onto them is lost on purpose, because the evidence that would admit "
                 "it is the evidence that admitted `r := n` above, and a lost right row costs less than an "
                 "added wrong one. The lazy programs are spec_check.lazy_functions, unchanged.")
        L.append("")
        by_label: Counter = Counter(label for hits in lazy.values() for label in hits)
        L.append("| lazy program | problems it answers at every point |")
        L.append("|---|---:|")
        for label, count in by_label.most_common():
            L.append(f"| {label} | {count} |")
        L.append("")
        L.append("| problem | function | points | lazy program that answers every point |")
        L.append("|---:|---|---:|---|")
        for tid, hits in sorted(lazy.items()):
            entry = pool.get(tid, {})
            L.append(f"| {tid} | `{entry.get('fn', '?')}` | {len(entry.get('points') or [])} | "
                     f"{'; '.join(hits)} |")
        L.append("")
    L.append("### Where the admitted programs were written for")
    L.append("")
    L.append("Programs come from every graded answer set, including held-out arms. The program never "
             "solved its own problem (its tests fail there); it is trained under the train problem's "
             "English only. The source problem is recorded in each row as an integer and a sha256, never as "
             "the task alias, because `preflight.py --pool` refuses a pool file that names a held-out alias "
             "anywhere in it, and that rule is kept rather than weakened.")
    L.append("")
    L.append("| source problem is | admitted programs |")
    L.append("|---|---:|")
    for label, count in sorted(origin.items()):
        L.append(f"| {label} | {count} |")
    L.append("")
    L.append("## Per answer set")
    L.append("")
    L.append("| answer set | table rows | wrong but proven | first seen here | admitted (copies) | "
             "duplicate pairs (copies) | no task file |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for tag in tags:
        i = per_set[tag]
        if not i["seven_kernels"]:
            L.append(f"| {tag} | {i['rows']} | not seven kernels | - | - | - | - |")
            continue
        L.append(f"| {tag} | {i['rows']} | {i['wrong_but_proven']} | {first_seen.get(tag, 0)} | "
                 f"{admitted_copies.get(tag, 0)} | {ambiguous_copies.get(tag, 0)} | {len(i['no_task_file'])} |")
    missing = [(tag, name) for tag, i in per_set.items() for name in i["no_task_file"]]
    if missing:
        L.append("")
        L.append("Rows counted wrong-but-proven whose `tasks/<name>.json` is missing, so nothing could be run:")
        L.append("")
        for tag, name in missing:
            L.append(f"- `{tag}/{name}`")
    L.append("")
    L.append("## Per target problem")
    L.append("")
    L.append(f"`points` is how many recorded assertions the target has; `draws` is how many of the "
             f"{args.n} random draws per point shape (every stated example drives {args.n} draws in turn) "
             "the program's specification agreed with the reference on, summed over the shapes; draws "
             "outside the specification's precondition, or where the reference raised, count for neither "
             "side, as in spec_check.check_task. Several programs on one target are distinct programs by "
             "`loop_filter.key`, which erases the task's name but not its parameter names or its "
             "precondition.")
    L.append("")
    L.append("| target | task | points | admitted programs | copies | from answer sets | draws |")
    L.append("|---:|---|---:|---:|---:|---|---|")
    for tid in sorted(by_target):
        rows = by_target[tid]
        tags_here = sorted({tag for o in rows for tag, _n in o["program"]["copies"]})
        draws = ", ".join(str(o["qualifying"][0]["draws"]) for o in rows)
        copies = sum(len(o["program"]["copies"]) for o in rows)
        L.append(f"| {tid} | `{rows[0]['qualifying'][0]['name']}` | {rows[0]['qualifying'][0]['points']} | "
                 f"{len(rows)} | {copies} | {', '.join(tags_here[:6])}{' ...' if len(tags_here) > 6 else ''} | "
                 f"{draws} |")
    low = [o for o in admitted if o["qualifying"][0]["draws"] < 10]
    L.append("")
    L.append(f"{len(low)} admitted row(s) agree with the reference on fewer than 10 draws"
             + (": " + ", ".join(f"{o['qualifying'][0]['task_id']} ({o['qualifying'][0]['draws']})" for o in low)
                if low else "")
             + ". The gate is the one every positive passes (spec_check status `agrees`, draws > 0); the count "
               "is here so a builder can weight by it.")
    L.append("")
    L.append("## The 10 largest per-signature groups")
    L.append("")
    L.append("| signature | distinct programs | copies | same-signature train candidates | admitted | "
             "duplicate pairs |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for sig, g in sorted(by_sig.items(), key=lambda kv: (-kv[1]["programs"], kv[0]))[:10]:
        L.append(f"| `{sig_text(sig)}` | {g['programs']} | {g['copies']} | {g['targets']} | {g['admitted']} | "
                 f"{g['ambiguous']} |")
    if ambiguous:
        L.append("")
        L.append("## Duplicate pairs found (one program, one specification, two problems)")
        L.append("")
        L.append("Not admitted under either problem. Written to the duplicates file for the decontamination "
                 "track: two train problems solved by one program whose specification agrees with both "
                 "references are, by the execution oracle, the same task.")
        L.append("")
        L.append("| problems | program from | copies |")
        L.append("|---|---|---:|")
        for o in ambiguous:
            ids = ", ".join(str(r["task_id"]) for r in o["qualifying"])
            L.append(f"| {ids} | {o['program']['tag']} (problem {o['program']['source_id']}) | "
                     f"{len(o['program']['copies'])} |")
    L.append("")
    L.append("## How the rows are used, and the weighting they still owe")
    L.append("")
    L.append("`python3 t/loop_dataset.py --from-samples ... --relabel-rows <this file>` appends the rows "
             "to the positives with `source: relabel` kept, through the same refusals as every other row "
             "(held-out under every alias, the same-task exclusions, the dev split: a row naming any of "
             "them stops the build, it is not dropped). The corpus builder then writes each one under the "
             "target problem's own `Problem:`/`Signature:` head.")
    L.append("")
    L.append("Nothing weights them yet. CodeIt's learning stage samples real solutions more often than "
             "relabeled ones (priority proportional to the share of demonstration outputs the program got "
             "right); its ablation A3, uniform sampling over the same buffer, fell from 49/400 to 38/400 on "
             "policy performance, \"indicating that the policy indeed forgets important experiences\" "
             "(https://arxiv.org/html/2402.04858, Table 2). The source field is what a later builder needs "
             "to weight real positives higher; until one does, a relabeled row counts exactly as much as a "
             "real one in the corpus.")
    L.append("")
    L.append("## What was learned")
    L.append("")
    rows_total = sum(i["wrong_but_proven"] for i in per_set.values())
    L.append(f"- {rows_total} wrong-but-proven rows are {len(distinct)} distinct programs: the population is "
             f"mostly the same attractors recited by many arms, {rows_total / max(1, len(distinct)):.1f} copies "
             "each on average.")
    L.append(f"- {len(admitted)} of {len(distinct)} distinct programs solve exactly one train problem "
             f"({100 * len(admitted) / max(1, len(distinct)):.0f} percent), over {len(by_target)} target "
             f"problems; {len(ambiguous)} solve two or more (the same function under several problem "
             f"statements) and {len(no_target)} solve none.")
    L.append(f"- Of {sum(o['targets_tried'] for o in outcomes)} (program, candidate) pairs, "
             f"{pair_tally.get('tests-fail', 0) + pair_tally.get('signature', 0)} fail the candidate's points, "
             f"{pair_tally.get('spec-disagrees', 0)} pass every point and then disagree with the reference on "
             "a draw: a program that passes three assertions is not yet a program that computes the function, "
             "and the reference check is not decorative.")
    L.append(f"- {len(lazy)} train candidates were refused because a lazy program answers every recorded "
             "point; a relabel onto them would have been a row about nothing.")
    L.append("- Two instruments were too weak on the first two runs and were tightened before any row was "
             "used: a target whose points a lazy program answers admitted `r := n` for the nth digit, and "
             "draws shaped like the first example alone admitted a lookup table for happy numbers. Both are "
             "properties of the evidence, not of the programs, and both are now refused by name.")
    L.append("")
    L.append("## What this differs from CodeIt in, and why")
    L.append("")
    L.append("CodeIt relabels to the realized output, so every valid program becomes data. Here the target "
             "must be an existing train problem, must be solved on every point, and the program's own "
             "specification must agree with that problem's reference solution on random draws and at its "
             "stated examples. The yield is therefore a small fraction of the population, and each admitted "
             "row carries a real problem's English, which is the thing locallm has to learn to read "
             "(internal/RESEARCH-NEXT-2026-09-20.md). A program that qualifies for two problems is not "
             "admitted for either.")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ main --

def graded_sets(roots: list[Path]) -> dict[str, Path]:
    """Every graded answer set under the roots, by tag.

    The graded sets live on two machines (the locallm arms were graded on one, the
    teacher sets on the other), so more than one root is read. A tag under two roots
    is one set only if its table's rows and its test verdicts are the same; the
    table's header carries the grading time, and one set graded twice six minutes
    apart with the same twenty rows is one set. Different rows or verdicts mean it was
    graded twice with different results, and it is refused by name.
    """
    sets: dict[str, Path] = {}

    def verdicts(d: Path) -> tuple:
        cols, cells = se.parse_kernel_table(d / "kernels.md")
        try:
            tests = json.loads((d / "tests.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise SystemExit(f"{d.name}: tests.json is not readable ({error})")
        return cols, cells, tests

    for root in roots:
        if not root.is_dir():
            raise SystemExit(f"{root} is not a directory of answer sets")
        for p in sorted(root.iterdir()):
            if not (p.is_dir() and (p / "kernels.md").exists() and (p / "tests.json").exists()
                    and (p / "tasks").is_dir()):
                continue
            other = sets.get(p.name)
            if other is not None:
                if verdicts(other) != verdicts(p):
                    raise SystemExit(f"{p.name}: graded differently under {other.parent} and {root} "
                                     f"(the table rows or the test verdicts differ); one set, one table, "
                                     f"or say which one with --root")
                continue
            sets[p.name] = p
    return sets


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", type=Path, required=True, help="the split whose train ids are candidates and "
                    "whose eval ids are refused; its pool version is the pool")
    ap.add_argument("--out", type=Path, required=True, help="the relabel pool file (JSONL) to write")
    ap.add_argument("--root", type=Path, nargs="+", default=[HERE / "out" / "spec-experiment"],
                    help="directories of graded answer sets, read only (repeatable: the sets are graded "
                         "on two machines)")
    ap.add_argument("--tags", nargs="*", default=None, help="answer sets to read (default: every graded one)")
    ap.add_argument("--n", type=int, default=100, help="random draws per (program, candidate) spec check")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--prompt-version", default="v5", choices=se.PROMPT_VERSIONS)
    ap.add_argument("--report", type=Path, default=HERE / "RELABEL-2026-09-25.md")
    ap.add_argument("--duplicates", type=Path, default=None,
                    help="where duplicate pairs go (default: beside --out, relabel-duplicates-<date>.jsonl)")
    args = ap.parse_args(argv)
    if args.n < 1:
        ap.error("--n must be positive")
    split = json.loads(args.split.read_text(encoding="utf-8"))
    train_ids = {int(i) for i in split.get("train_ids", split.get("used_task_ids", []))}
    gates = load_gates(split, args.split)
    if train_ids & gates.held_out:
        raise SystemExit(f"{args.split}: train and eval ids overlap; refusing")
    pool_name = split.get("pool", "v1")
    pool = se.pool(pool_name)
    if split.get("pool_size") is not None and int(split["pool_size"]) != len(pool):
        raise SystemExit(f"{args.split} names a pool of {split['pool_size']} problems and pool {pool_name} here "
                         f"has {len(pool)}: the untracked pool data is missing, and a shrunken pool would "
                         f"silently try fewer candidates; run where the data is")
    candidates = {tid for tid in pool if tid in train_ids and not gates.forbids(tid)}
    lazy = undiscriminating(pool, candidates)
    index = target_index(pool, train_ids, gates, frozenset(lazy))
    sets = graded_sets(args.root)
    tags = args.tags if args.tags is not None else sorted(sets)
    if not tags:
        raise SystemExit(f"no graded answer set under {', '.join(map(str, args.root))}")
    programs, per_set = [], {}
    for tag in tags:
        d = sets.get(tag)
        if d is None:
            raise SystemExit(f"{tag}: no graded answer set of that name (kernels.md, tests.json and tasks/) "
                             f"under {', '.join(map(str, args.root))}; a set never graded has no proven rows")
        progs, info = wrong_but_proven(tag, d)
        per_set[tag] = info
        programs.extend(progs)
    distinct = distinct_programs(programs)
    print(f"{len(tags)} answer sets, {sum(i['wrong_but_proven'] for i in per_set.values())} wrong-but-proven "
          f"rows, {len(distinct)} distinct programs; pool {pool_name} with {len(index)} signatures over "
          f"{sum(map(len, index.values()))} train candidates ({len(lazy)} refused: their own points cannot "
          f"reject a lazy program)", flush=True)
    outcomes = []
    for k, program in enumerate(distinct, 1):
        targets = targets_for(program, index, gates)
        outcome = relabel_program(program, targets, pool, args.n, args.seed)
        outcomes.append(outcome)
        if outcome["kind"] != "no-target" or k % 100 == 0:
            hit = outcome["qualifying"]
            print(f"[{k}/{len(distinct)}] {program['tag']}/{program['name']}: {outcome['kind']}"
                  + (f" -> {', '.join(str(r['task_id']) for r in hit)}" if hit else "")
                  + f" ({outcome['targets_tried']} candidates)", flush=True)
    rows = [pool_row(o, pool, pool_name, args.n, args.seed, args.prompt_version)
            for o in outcomes if o["kind"] == "admitted"]
    dups = [duplicate_row(o, pool_name) for o in outcomes if o["kind"] == "ambiguous"]
    # Every row is checked once more the way the corpus builder will check it, on the whole row's text:
    # a relabel that names a held-out, listed or dev problem anywhere is a bug here, not a row to drop.
    for row in rows:
        bad = loop_filter.validate_training_data(json.dumps(row, sort_keys=True), gates.held_out | gates.dev,
                                                 names=[row["task"]], task_ids=[row["task_id"]])
        if not bad.ok or gates.forbids(row["task_id"]):
            raise SystemExit(f"a relabel row for {row['task_id']} names a gated problem: "
                             f"{loop_filter.held_out_detail(bad.held_out) if bad.held_out else loop_filter.same_task_detail(bad)}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    dup_path = args.duplicates or args.out.with_name(args.out.name.replace("relabel-", "relabel-duplicates-", 1)
                                                     if args.out.name.startswith("relabel-")
                                                     else f"duplicates-{args.out.name}")
    dup_path.parent.mkdir(parents=True, exist_ok=True)
    dup_path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in dups), encoding="utf-8")
    write_report(args.report, args, args.split, pool_name, len(pool), tags, per_set, programs, distinct,
                 outcomes, index, gates, args.out, dup_path, lazy, pool)
    kinds = Counter(o["kind"] for o in outcomes)
    print(f"admitted {kinds.get('admitted', 0)} rows over {len({r['task_id'] for r in rows})} target problems; "
          f"{kinds.get('ambiguous', 0)} duplicate pairs; {kinds.get('no-target', 0)} programs with no target")
    print(f"wrote {args.out}, {dup_path}, {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
