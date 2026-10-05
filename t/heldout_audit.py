#!/usr/bin/env python3
"""t/heldout_audit.py -- do the training rows hold a held-out problem under another name? (2026-10-05)

    python3 t/heldout_audit.py --rows ROWS.jsonl [ROWS.jsonl ...] [--json OUT] [--jobs N] [--refuse-gpl]
    python3 t/heldout_audit.py --rows ROWS.jsonl --keep CLEAN.jsonl      # also write the rows nothing flags
    python3 t/heldout_audit.py --rows NEW.jsonl --panels                 # the gate of a row build (see below)
    python3 t/heldout_audit.py --rows ... --write-policy t/decontamination-rows-2026-10-05.json

Exit status 0 when no row is flagged and 1 when one is: the last gate of a row build, whatever route a row
arrived by.

`--panels` is how a row build uses it. The problems this audit found in the rows of 2026-10-05 left the panels
(t/decontamination-rows-2026-10-05.json: the clean 200 became the clean 182, the 100 dev problems 95), so a row
that matches one of them, or one of the 32 that left on 2026-09-21, costs no measurement and is not refused; a
row that matches a problem still in a panel is, and the build fails. The panels only ever shrank for rows a
model had already been trained on; a new row does not get to shrink them.

Why it exists. Every gate before this one sat on a route: the corpus builder matched names (`mbpp_N`,
`dafny_synthesis_task_id_N`), the lift ran a twin check on what it lifted. On 2026-10-05 the rows every
fine-tuned model had trained on were read instead, and held 18 of the clean 200 under other names:
`vericoding_dd0736__replaceChars` is MBPP 474 by way of MBPP-DFY and DafnyBench; `vericoding_dj0091__cubeElement`
is MBPP 447 by way of Verus-Bench, which "Translated from MBPP-DFY-153" (its README); the lift had refused both
as twins and a rechecked copy of each came back through a set the screen never saw; a teacher answered the
specification of MBPP 804 because nothing mapped the prompt's source to a problem. String matching does not
survive a translation (Yang et al., arXiv:2311.04850: "simple variations of test data (e.g., paraphrasing,
translation) can easily bypass these decontamination measures"). A check on the rows themselves does not care
how a row got there. Research receipt b3750197e472.

Two readings, both of every row.

  lineage  a row that names a vericoding task (`vericoding_XX0000`, anywhere in the row) whose source the
           benchmark records as an MBPP task (t/vericoding-mbpp-lineage.json), or a `dafny_synthesis_task_id_N`
           name, is that MBPP problem's own formalisation. Flagged when the problem is held out or in the dev
           split, whatever the program computes: the formalisation of MBPP 472 (two neighbours somewhere) is not
           the function MBPP 472's tests ask for, and it is still that problem's text read by someone else.
  twin     every fenced t program in the row, in the answer and in the prompt (a debug row shows a failing
           program), is run on the test points of every gated problem. A candidate passes at least one point
           and fails none; a point its `requires` excludes is not a failure (`isPrime` requires n >= 2 and MBPP
           605 tests -1010, which is how the lift's gate never met the pair). Each candidate is then asked on
           100 drawn inputs by the lift's own rule (t/twin_draws.py, differential testing against the reference
           after EvalPlus, arXiv:2305.01210): it is the problem's twin unless the two answer at least 10% of
           the inputs both answer differently. MBPP often passes an array with its length; a program of the
           same task takes the array alone and its arity never matches, so a gated problem with such an
           argument is also asked without it, the argument set to the sequence's length in every drawn input.

Nothing is read by hand and nothing is excused: a row the rule flags is flagged, including the coincidences
(a program that returns `true` is the twin of MBPP 899, whose reference returns True). The cost is a few
problems; what it buys is a panel nobody has to argue about.

`--refuse-gpl` also flags a row whose lineage is MBPP-DFY (github.com/Mondego/dafny-synthesis, GPL-3.0),
by either route: a redistribution or a translation does not change the licence of the original
(internal/RELEASE-PROVENANCE-2026-10-01.md), and the filter of 2026-10-01 matched the name alone.

A third panel since the same day: the problems only the wider reader reads (pool v7's additions,
t/spec_experiment.py wider_pool), which no split names and no model was trained on. They are gated as "wider";
the ones the published model's rows already match, and three the reader cannot ask faithfully, are recorded in
t/decontamination-wider-2026-10-05.json; the rest are a held-out panel from their first day (`wider_clean()`).

What it cannot see: the same task under a signature that differs by more than a length argument (arguments in
another order, a pair where the problem takes two values) when the benchmark records no lineage; a problem
whose reference does not run, or whose inputs no draw can produce, keeps every candidate (the conservative
side); and it compares against the references MBPP ships, some of which are wrong (MBPP 605's calls 4 a prime).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import multiprocessing as mp
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import behavioural_decontam as bd                               # noqa: E402
import loop_filter                                              # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402
import twin_draws                                               # noqa: E402

LINEAGE = HERE / "vericoding-mbpp-lineage.json"
SPLIT = HERE / "out" / "loop" / "split-v5.json"
DEV = HERE / "r12-dev-ids.json"
POLICY = HERE / "decontamination-rows-2026-10-05.json"
WIDER_POLICY = HERE / "decontamination-wider-2026-10-05.json"
SOURCES = ("https://arxiv.org/abs/2311.04850", "https://ar5iv.labs.arxiv.org/html/2305.01210",
           "https://raw.githubusercontent.com/microsoft/verus-proof-synthesis/main/benchmarks/Verus-Bench/README.md")
RULE = ("a training row is flagged for a gated problem (held-out or dev) when it names that problem's own "
        "formalisation (lineage), or holds a t program, in its answer or its prompt, that passes at least one of the "
        "problem's test points, fails none, and on 100 drawn inputs answers fewer than 10% of the inputs both answer "
        "differently from the problem's reference (twin; t/twin_draws.py), the problem's length argument left out "
        "where it has one")

_STEM = re.compile(r"vericoding_([A-Za-z]{2}\d{4})")
_DFY = re.compile(r"dafny[-_]synthesis[-_]task[-_]id[-_](\d+)", re.I)
_FENCE = re.compile(r"```t\n(.*?)```", re.S)
_QUIET = ("pass", "requires-excluded")


# ---------------------------------------------------------------- lineage --

def lineage(path: Path = LINEAGE) -> dict[str, dict]:
    """vericoding id (lower case) -> {"mbpp": N, "via": family, "source_id": ...}. Refused when the file is
    missing or empty: a table that silently loads as nothing admits every row it exists to stop."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = data.get("ids")
    if data.get("schema") != 1 or not isinstance(ids, dict) or not ids:
        raise ValueError(f"{path}: not a lineage table")
    return {k.lower(): v for k, v in ids.items()}


def strings(value):
    """Every string in a row, however nested (a prompt is a list of messages)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from strings(v)


def named_mbpp(row: dict, table: dict[str, dict]) -> dict[int, str]:
    """MBPP task id -> how the row names it, for every vericoding task and MBPP-DFY name anywhere in the row."""
    out: dict[int, str] = {}
    for text in strings(row):
        for stem in _STEM.findall(text):
            hit = table.get(stem.lower())
            if hit:
                out.setdefault(int(hit["mbpp"]), f"vericoding_{stem} is {hit['source_id']}")
        for n in _DFY.findall(text):
            out.setdefault(int(n), f"dafny_synthesis_task_id_{n}")
    return out


def gpl_origin(row: dict, table: dict[str, dict]) -> str | None:
    """How the row descends from MBPP-DFY (GPL-3.0), or None."""
    named = named_mbpp(row, table)
    return next(iter(named.values()), None)


def blocks(row: dict) -> list[str]:
    """The distinct fenced t programs of a row, answer and prompt alike."""
    seen, out = set(), []
    for text in strings(row):
        for block in _FENCE.findall(text):
            if block not in seen:
                seen.add(block)
                out.append(block)
    return out


# ------------------------------------------------------------------- twin --

def gates(split_path: Path = SPLIT, dev_path: Path = DEV, wider: bool = True) -> dict[int, str]:
    """problem id -> "held-out" | "dev" | "wider", for every gated problem, with test points or without."""
    eval_ids = {int(i) for i in json.loads(Path(split_path).read_text(encoding="utf-8"))["eval_ids"]}
    out = {int(tid): "wider" for tid in (se.wider_pool() if wider else {})}
    out.update({int(tid): "dev" for tid in loop_filter.r12_dev_ids(dev_path)})
    out.update({tid: "held-out" for tid in eval_ids})
    return out


def gated_problems(pool: dict, split_path: Path = SPLIT, dev_path: Path = DEV) -> dict[int, tuple[dict, str]]:
    """problem id -> (pool entry, its gate), for every gated problem the pool holds with test points."""
    return {tid: (pool[tid], gate) for tid, gate in sorted(gates(split_path, dev_path).items())
            if tid in pool and pool[tid].get("points")}


def length_arguments(entry: dict) -> list[tuple[int, int]]:
    """(i, j) for every int argument i that equals the length of sequence argument j in every test point."""
    points = entry["points"]
    arity = len(points[0]["args"])
    out = []
    for i in range(arity):
        if not all(len(p["args"]) == arity and p["args"][i][0] == "int" for p in points):
            continue
        for j in range(arity):
            if j != i and all(p["args"][j][0] == "seq" and isinstance(p["args"][j][1], list)
                              and len(p["args"][j][1]) == p["args"][i][1] for p in points):
                out.append((i, j))
                break
    return out


def without_argument(points: list[dict], i: int) -> list[dict]:
    out = []
    for point in points:
        q = copy.deepcopy(point)
        del q["args"][i]
        out.append(q)
    return out


def quiet(task: dict, points: list[dict]) -> list[str] | None:
    """The verdicts when the program passes at least one point and fails none, else None."""
    verdicts = []
    for point in points:
        try:
            verdict = se.run_point(task, point)["verdict"]
        except Exception as error:                              # noqa: BLE001 -- one program's crash is that program failing
            verdict = f"raised {type(error).__name__}"
        if verdict not in _QUIET:
            return None
        verdicts.append(verdict)
    return verdicts if "pass" in verdicts else None


def candidates(task: dict, gated: dict[int, tuple[dict, str]]) -> list[dict]:
    """Every gated problem this program stays quiet on, with the argument left out when that is how."""
    out = []
    for tid, (entry, gate) in gated.items():
        verdicts = quiet(task, entry["points"])
        if verdicts is not None:
            out.append({"problem": tid, "gate": gate, "points": verdicts, "dropped": None})
            continue
        for i, j in length_arguments(entry):
            verdicts = quiet(task, without_argument(entry["points"], i))
            if verdicts is not None:
                out.append({"problem": tid, "gate": gate, "points": verdicts, "dropped": [i, j]})
                break
    return out


def draw_check(task: dict, tid: int, entry: dict, runner: bd.Runner, dropped: list[int] | None = None) -> dict:
    """twin_draws.draw_check; with `dropped` = [i, j] the problem's argument i is set to the length of its
    sequence j in every drawn input and left out of the program's call (same counts, same verdicts)."""
    if dropped is None:
        return twin_draws.draw_check(task, tid, entry, runner)
    i, j = dropped
    check = {"problem": int(tid), "draws": 0, "answered_by_both": 0, "agreed": 0, "differed": 0,
             "program_silent": 0, "reference_silent": 0, "no_t_reading": 0, "unfaithful": 0}
    if runner.reference(tid) is None:
        return twin_draws._decided(check, "no reference", runner.why_not_run(tid))
    kinds = [k for k, _v in entry["points"][0]["args"]]
    draws = bd.draws_for(tid, entry, n=twin_draws.DRAWS, seed=twin_draws.SEED)
    if draws is None:
        return twin_draws._decided(check, "cannot draw", f"spec_check.draw has no draw for the kinds {kinds}")
    expected = entry["points"][0]["expected"]
    shapes = runner.shapes[tid]
    for args in draws:
        check["draws"] += 1
        args = list(args)
        args[i] = len(args[j])
        if not all(twin_draws.faithful(a, s) for a, s in zip(args, shapes)):
            check["unfaithful"] += 1
            continue
        mine = twin_draws.program_answer(task, kinds[:i] + kinds[i + 1:], args[:i] + args[i + 1:], expected)
        if mine[0] != "ok":
            check["program_silent"] += 1
            continue
        theirs = runner.call(tid, tuple(args))
        if theirs[0] != "ok":
            check["reference_silent"] += 1
            continue
        reading = twin_draws.read_answer(theirs[1], mine[1])
        if reading is None:
            check["no_t_reading"] += 1
            continue
        check["answered_by_both"] += 1
        if reading == mine[1]:
            check["agreed"] += 1
            continue
        check["differed"] += 1
        check.setdefault("witness", {"input": bd._brief(list(args)), "program": bd._brief(mine[1]),
                                     "reference": bd._brief(theirs[1])})
    if check["differed"]:
        fraction = check["differed"] / check["answered_by_both"]
        check["differ_fraction"] = round(fraction, 4)
        return twin_draws._decided(check, "near twin" if fraction < twin_draws.NEAR_TWIN_FRACTION else "differs")
    if check["answered_by_both"]:
        return twin_draws._decided(check, "agrees")
    return twin_draws._decided(check, "no draw answered by both", runner.why_not_run(tid))


# ----------------------------------------------------------------- panels --

def policy(path: Path = POLICY) -> dict:
    """The checked-in record of what this audit removed from the panels. Refused when it does not say what it
    claims: a policy that loads as empty would put 18 contaminated problems back in the held-out panel."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    held, dev = data.get("overlap_eval_ids"), data.get("dev_overlap_ids")
    if data.get("schema") != 1 or not isinstance(held, list) or not isinstance(dev, list) or not held:
        raise ValueError(f"{path}: not a row-audit policy")
    return data


def wider_flagged(path: Path = WIDER_POLICY) -> set[int]:
    """The wider reader's problems that never enter its panel: the ones the published model's rows already
    matched, and the ones whose own reference does not reproduce its own tests once they are read the reader's
    way (MBPP 222's `(1, 2, "4")` is a tuple of mixed types, and the reader's "4" is the character 52)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    flagged, unfaithful = data.get("flagged_ids"), data.get("unfaithful_ids", [])
    if data.get("schema") != 1 or not isinstance(flagged, list) or not isinstance(unfaithful, list):
        raise ValueError(f"{path}: not a wider-panel record")
    return {int(i) for i in flagged} | {int(i) for i in unfaithful}


def wider_clean(path: Path = WIDER_POLICY) -> set[int]:
    """The wider panel: pool v7's additions without the ones the rows of 2026-10-05 matched."""
    return set(se.wider_pool()) - wider_flagged(path)


def removed_ids(path: Path = POLICY, wider_path: Path = WIDER_POLICY) -> set[int]:
    """Every problem already out of a panel: this audit's held-out and dev ids, the 32 of 2026-09-21, and the
    wider reader's problems that never entered its panel."""
    data = policy(path)
    return ({int(i) for i in data["overlap_eval_ids"]} | {int(i) for i in data["dev_overlap_ids"]}
            | set(loop_filter.decontamination().overlap_eval_ids)
            | (wider_flagged(wider_path) if Path(wider_path).exists() else set()))


def clean_182(eval_ids: set[int], path: Path = POLICY) -> set[int]:
    """The held-out panel since 2026-10-05: the clean 200 without the problems the rows held."""
    import score_heldout
    return score_heldout.clean_eval_ids(set(eval_ids)) - {int(i) for i in policy(path)["overlap_eval_ids"]}


def dev_95(dev_path: Path = DEV, path: Path = POLICY) -> set[int]:
    """The dev panel since 2026-10-05."""
    return set(loop_filter.r12_dev_ids(dev_path)) - {int(i) for i in policy(path)["dev_overlap_ids"]}


# ------------------------------------------------------------------ audit --

_GATED: dict[int, tuple[dict, str]] | None = None


def _init(pool_name: str, split_path: str, dev_path: str) -> None:
    global _GATED
    _GATED = gated_problems(se.pool(pool_name), Path(split_path), Path(dev_path))


def _candidates_of(item: tuple[str, str]) -> tuple[str, list[dict] | None]:
    digest, block = item
    try:
        task = surface.parse(block)
    except Exception:                                           # noqa: BLE001 -- not a t program: nothing to run
        return digest, None
    if not task.get("body"):
        return digest, []                                       # a question (a specification with an empty body)
    return digest, candidates(task, _GATED or {})


def read_rows(paths: list[Path]) -> list[tuple[str, int, dict]]:
    out = []
    for path in paths:
        for k, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines()):
            if line.strip():
                out.append((Path(path).name, k, json.loads(line)))
    return out


def audit(rows: list[tuple[str, int, dict]], *, pool_name: str = "v7", split_path: Path = SPLIT,
          dev_path: Path = DEV, table: dict[str, dict] | None = None, jobs: int = 8,
          refuse_gpl: bool = False, hung_path: Path | None = None) -> dict:
    """{"findings": [...], "flagged": sorted (file, line) pairs, "programs": N, "unparsed": N}. A finding is one
    (row, problem, why) with its evidence; a row can carry several."""
    table = lineage() if table is None else table
    pool = se.pool(pool_name)
    gate_of = gates(split_path, dev_path)
    findings: list[dict] = []
    programs: dict[str, str] = {}
    holders: dict[str, list[int]] = {}
    for index, (file, line, row) in enumerate(rows):
        for tid, how in named_mbpp(row, table).items():
            if tid in gate_of:
                findings.append({"row": index, "problem": tid, "gate": gate_of[tid], "why": "lineage", "detail": how})
        if refuse_gpl:
            how = gpl_origin(row, table)
            if how:
                findings.append({"row": index, "problem": None, "gate": "licence", "why": "gpl",
                                 "detail": f"{how}: MBPP-DFY, GPL-3.0 at the source"})
        for block in blocks(row):
            digest = hashlib.sha256(block.encode("utf-8")).hexdigest()[:16]
            programs.setdefault(digest, block)
            holders.setdefault(digest, []).append(index)
    items = sorted(programs.items())
    if jobs > 1 and len(items) > 32:
        with mp.Pool(jobs, initializer=_init, initargs=(pool_name, str(split_path), str(dev_path))) as workers:
            found = dict(workers.imap_unordered(_candidates_of, items, chunksize=8))
    else:
        _init(pool_name, str(split_path), str(dev_path))
        found = dict(_candidates_of(item) for item in items)
    runner = twin_draws.runner(pool, hung_path)
    for digest in sorted(found):
        for cand in found[digest] or []:
            tid = cand["problem"]
            check = draw_check(surface.parse(programs[digest]), tid, pool[tid], runner, cand["dropped"])
            if not check["twin"]:
                continue
            detail = {k: check[k] for k in ("verdict", "agreed", "answered_by_both", "program_silent", "why", "witness")
                      if k in check}
            detail.update(points=cand["points"], program=digest,
                          **({"without_argument": cand["dropped"][0]} if cand["dropped"] else {}))
            for index in holders[digest]:
                findings.append({"row": index, "problem": tid, "gate": cand["gate"], "why": "twin", "detail": detail})
    for finding in findings:
        file, line, row = rows[finding["row"]]
        finding.update(file=file, line=line, name=row.get("name"), kind=row.get("kind"))
    flagged = sorted({(f["file"], f["line"]) for f in findings})
    return {"findings": findings, "flagged": flagged, "rows": len(rows), "programs": len(programs),
            "unparsed": sum(1 for v in found.values() if v is None)}


def by_problem(findings: list[dict]) -> dict[tuple[str, int], dict]:
    """(gate, problem) -> {"why": sorted reasons, "rows": N, "names": a few row names}."""
    out: dict[tuple[str, int], dict] = {}
    for f in findings:
        if f["problem"] is None:
            continue
        e = out.setdefault((f["gate"], f["problem"]), {"why": set(), "rows": set(), "names": set()})
        e["why"].add(f["why"])
        e["rows"].add((f["file"], f["line"]))
        if f.get("name"):
            e["names"].add(str(f["name"]))
    return {k: {"why": sorted(v["why"]), "rows": len(v["rows"]), "names": sorted(v["names"])[:4]}
            for k, v in sorted(out.items())}


def render(result: dict) -> str:
    lines = [f"{result['rows']} rows, {result['programs']} distinct t programs ({result['unparsed']} did not parse); "
             f"{len(result['flagged'])} rows flagged"]
    table = by_problem(result["findings"])
    if table:
        lines += ["", "| gate | problem | why | rows | e.g. |", "|---|---:|---|---:|---|"]
        lines += [f"| {gate} | {tid} | {', '.join(v['why'])} | {v['rows']} | {', '.join(v['names'][:2])} |"
                  for (gate, tid), v in table.items()]
    licence = {(f["file"], f["line"]) for f in result["findings"] if f["why"] == "gpl"}
    if licence:
        lines += ["", f"{len(licence)} rows descend from MBPP-DFY (GPL-3.0 at the source)"]
    return "\n".join(lines)


def policy_of(result: dict, row_files: list[Path], split_path: Path = SPLIT) -> dict:
    """The record of a whole audit: which problems leave which panel, and the rows that say so."""
    import score_heldout
    eval_ids = {int(i) for i in json.loads(Path(split_path).read_text(encoding="utf-8"))["eval_ids"]}
    clean = score_heldout.clean_eval_ids(eval_ids)
    table = by_problem(result["findings"])
    held = sorted(tid for (gate, tid) in table if gate == "held-out")
    return {
        "schema": 1,
        "about": "Problems of the held-out and dev panels that the training rows held under another name, found by "
                 "t/heldout_audit.py on every row file a measured model trained on. overlap_eval_ids leave the clean "
                 "200 (the clean 182); dev_overlap_ids leave the 100 dev problems (95). Human-readable version with "
                 "the restated scores: t/DECONTAMINATION-2026-10-05.md",
        "rule": RULE,
        "sources": list(SOURCES),
        "audited": [{"file": Path(f).name, "sha256": hashlib.sha256(Path(f).read_bytes()).hexdigest(),
                     "rows": sum(1 for line in Path(f).read_text(encoding="utf-8").splitlines() if line.strip())}
                    for f in row_files],
        "overlap_eval_ids": [tid for tid in held if tid in clean],
        "flagged_already_excluded": [tid for tid in held if tid not in clean],
        "dev_overlap_ids": sorted(tid for (gate, tid) in table if gate == "dev"),
        "evidence": {f"{gate}:{tid}": v for (gate, tid), v in table.items() if gate in ("held-out", "dev")},
    }


def wider_policy_of(result: dict, row_files: list[Path]) -> dict:
    """The record of the wider panel's first day: which of pool v7's additions the rows already matched."""
    table = {tid: v for (gate, tid), v in by_problem(result["findings"]).items() if gate == "wider"}
    return {
        "schema": 1,
        "about": "The MBPP problems only the wider reader reads (t/spec_experiment.py wider_pool) that the training rows "
                 "of 2026-10-05 already matched, by t/heldout_audit.py's lineage and twin readings. They never enter the "
                 "wider panel; the rest are held out from their first day. t/PREDICT-2026-10-05-wider-reader.md",
        "rule": RULE,
        "audited": [{"file": Path(f).name, "sha256": hashlib.sha256(Path(f).read_bytes()).hexdigest(),
                     "rows": sum(1 for line in Path(f).read_text(encoding="utf-8").splitlines() if line.strip())}
                    for f in row_files],
        "problems": len(se.wider_pool()),
        "flagged_ids": sorted(table),
        "evidence": {str(tid): v for tid, v in sorted(table.items())},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, nargs="+", required=True, help="training rows, one JSON object a line")
    ap.add_argument("--pool", default="v7", help="v7 (default) holds the wider reader's problems; v5 audits without them")
    ap.add_argument("--split", type=Path, default=SPLIT)
    ap.add_argument("--dev", type=Path, default=DEV)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--refuse-gpl", action="store_true", help="also flag rows that descend from MBPP-DFY (GPL-3.0)")
    ap.add_argument("--json", type=Path, help="write every finding here")
    ap.add_argument("--keep", type=Path, help="write the rows nothing flags here (one --rows file only)")
    ap.add_argument("--panels", nargs="?", type=Path, const=POLICY, default=None, metavar="POLICY",
                    help="a match with a problem already out of the panels is reported and not refused")
    ap.add_argument("--write-policy", type=Path, help="write the panels' record from this audit (every row file "
                                                      "a measured model trained on, no --panels)")
    ap.add_argument("--write-wider-policy", type=Path, help="write the wider panel's record (the published model's rows)")
    a = ap.parse_args(argv)
    if a.keep and len(a.rows) != 1:
        raise SystemExit("heldout_audit: --keep takes one --rows file")
    if a.write_policy and a.panels:
        raise SystemExit("heldout_audit: --write-policy records a whole audit; it does not take --panels")
    rows = read_rows(a.rows)
    result = audit(rows, pool_name=a.pool, split_path=a.split, dev_path=a.dev, jobs=a.jobs, refuse_gpl=a.refuse_gpl,
                   hung_path=(a.json.with_suffix(".twin-hung.jsonl") if a.json else None))
    if a.panels:
        gone = removed_ids(a.panels)
        result["out_of_the_panels"] = [f for f in result["findings"] if f["problem"] in gone]
        result["findings"] = [f for f in result["findings"] if f["problem"] not in gone]
        result["flagged"] = sorted({(f["file"], f["line"]) for f in result["findings"]})
    print(render(result))
    if a.panels:
        print(f"\n{len({(f['file'], f['line']) for f in result['out_of_the_panels']})} rows match a problem already "
              f"out of the panels ({a.panels.name}); not refused")
    if a.json:
        a.json.write_text(json.dumps({"rule": RULE, "sources": SOURCES, **result}, indent=1) + "\n", encoding="utf-8")
    if a.write_policy:
        a.write_policy.write_text(json.dumps(policy_of(result, a.rows, a.split), indent=1) + "\n", encoding="utf-8")
        print(f"wrote {a.write_policy}")
    if a.write_wider_policy:
        if a.panels:
            raise SystemExit("heldout_audit: --write-wider-policy records a whole audit; it does not take --panels")
        a.write_wider_policy.write_text(json.dumps(wider_policy_of(result, a.rows), indent=1) + "\n", encoding="utf-8")
        print(f"wrote {a.write_wider_policy}")
    if a.keep:
        bad = {line for _file, line in result["flagged"]}
        kept = [text for k, text in enumerate(a.rows[0].read_text(encoding="utf-8").splitlines())
                if text.strip() and k not in bad]           # verbatim: a kept row is the row that was audited
        a.keep.write_text("".join(k + "\n" for k in kept), encoding="utf-8")
        print(f"kept {len(kept)} of {len(rows)} rows in {a.keep}")
    return 1 if result["flagged"] else 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
