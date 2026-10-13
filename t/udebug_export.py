#!/usr/bin/env python3
"""udebug_export.py: the submission bundle. Every problem in the bank gets one line in INDEX.jsonl; a problem whose
accepted program reproduces every stored case again, twice, under two fixed hash seeds, gets `<out>/<judge>/<id>.py`
beside `<id>.json` (the evidence: cases, the slowest case, the lane and model, the program's sha256).

    python3 t/udebug_export.py --bank t/out/udebug/bank.jsonl --corpus t/out/udebug-bulk-20261011 \\
        --lanes 't/out/udebug/teacher-*' --out t/out/udebug-solutions --judges UVa --jobs 2

What "solved" means here, and only this: the program's output equals the judge's stored accepted output on every
stored input, on three runs (the lane's grading run and the two confirmation runs here), compared with trailing
blank lines and trailing spaces ignored. It is not a proof against the statement, and the online judge's hidden
data and time limit are beyond what a local check can promise; `max_case_s` is the reading to compare with a time
limit. The second seed matters because Python randomizes str hashing per process
(docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED), so a program whose output depends on the order of a
set or dict of strings can pass once and fail on resubmission.

A problem without an accepted sample gets its best failure: the status (fail, error, timeout, no-fences), the case
and the first difference, from the most informative attempt; that is the repair round's input.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import glob
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import udebug_gate as ug  # noqa: E402

RANK = {"pass": 0, "fail": 1, "error": 2, "timeout": 3, "no-fences": 4}


def load_bank(path: Path, judges: set[str]) -> dict[tuple[str, str], dict]:
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if judges and r["judge"] not in judges:
                continue
            out[(r["judge"], r["id"])] = r
    return out


EXCLUDED_PROVIDERS = ("openai",)


def lane_provider(lane_p: Path) -> str | None:
    """The provider one record of the lane names (every sample of a lane shares it)."""
    probe = next(iter(lane_p.glob("*/s*/record.json")), None)
    if probe is None:
        return None
    try:
        return json.loads(probe.read_text(encoding="utf-8")).get("provider")
    except (OSError, ValueError):
        return None


def scan_lanes(patterns: list[str], excluded: set[str] | None = None) -> dict[tuple[str, str], list[dict]]:
    """Every result.json under the lanes, keyed by (judge, id); each carries its lane name and sample dir. A lane
    written by an excluded provider (OpenAI: the uDebug work is dawnr's own and never touches it, by the user's
    rule of 2026-10-13) is left out and its name recorded in `excluded`."""
    found = collections.defaultdict(list)
    for pat in patterns:
        for lane in sorted(glob.glob(pat)):
            lane_p = Path(lane)
            if lane_provider(lane_p) in EXCLUDED_PROVIDERS:
                if excluded is not None:
                    excluded.add(lane_p.name)
                print(f"excluded lane {lane_p.name}: provider {lane_provider(lane_p)}", file=sys.stderr)
                continue
            for r in lane_p.glob("*/s*/result.json"):
                try:
                    o = json.loads(r.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if o.get("parse") != "python":
                    o.setdefault("judge", None)
                o["lane"] = lane_p.name
                o["sample_dir"] = str(r.parent)
                found[(o["judge_name"], o["id"])].append(o)
    return found


def status_of(o: dict) -> str:
    if o.get("parse") == "no-fences" or o.get("parse") is None:
        return "no-fences"
    j = o.get("judge") or {}
    return j.get("status") or "no-fences"


def best_failure(results: list[dict]) -> dict:
    o = min(results, key=lambda r: (RANK.get(status_of(r), 9), r["sample_dir"]))
    j = o.get("judge") or {}
    return {"status": status_of(o), "case": j.get("case"), "first_difference": j.get("first_difference"),
            "passed": j.get("passed"), "total": j.get("total"), "lane": o["lane"], "sample_dir": o["sample_dir"]}


def model_of(sample_dir: str) -> str:
    try:
        rec = json.loads((Path(sample_dir) / "record.json").read_text(encoding="utf-8"))
        return rec.get("model") or ""
    except (OSError, ValueError):
        return ""


def est_time(o: dict, prev: dict | None) -> float:
    """The sample's slowest case as the lane's grading measured it, or as the previous export measured this same
    sample; unknown sorts last, so a sample with a measurement is tried first."""
    t = (o.get("judge") or {}).get("max_case_s")
    if t is None and prev and prev.get("sample_dir") == o["sample_dir"]:
        t = prev.get("max_case_s")
    return t if t is not None else 1e9


def confirm(key: tuple[str, str], rec: dict, accepted: list[dict], corpus: Path, out: Path, seeds: list[int],
            timeout: float, prev: dict | None = None) -> dict:
    judge, ident = key
    tests = corpus / rec["tests_dir"]
    runs = []
    chosen = None
    # the accepted samples fastest first; the first that passes both seeds is the solution
    for o in sorted(accepted, key=lambda r: (est_time(r, prev), r["sample_dir"])):
        prog = Path(o["sample_dir"]) / f"p{ident}.py"
        if not prog.is_file():
            continue
        ok = True
        these = []
        for seed in seeds:
            env = dict(os.environ, PYTHONHASHSEED=str(seed))
            j = ug.judge_python(prog, tests, timeout, env=env)
            these.append({"seed": seed, **{k: j.get(k) for k in ("status", "passed", "total", "skipped", "case",
                                                                  "first_difference", "max_case_s")}})
            if j["status"] != "pass":
                ok = False
                break
        runs.append({"sample_dir": o["sample_dir"], "lane": o["lane"], "runs": these, "confirmed": ok})
        if ok:
            chosen = o
            break
    entry = {"judge": judge, "id": ident, "title": rec.get("title"), "n_files": rec.get("n_files"),
             "n_scored": rec.get("n_scored"), "in_bytes": rec.get("in_bytes"), "out_bytes": rec.get("out_bytes"),
             "split": rec.get("split"), "attempts": runs}
    if chosen is None:
        entry["status"] = "accepted-but-not-confirmed"
        return entry
    prog = Path(chosen["sample_dir"]) / f"p{ident}.py"
    src = prog.read_bytes()
    dest_dir = out / judge
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / f"{ident}.py").write_bytes(src)
    max_s = max(r["max_case_s"] or 0.0 for r in runs[-1]["runs"])
    entry.update({"status": "solved", "lane": chosen["lane"], "sample_dir": chosen["sample_dir"],
                  "model": model_of(chosen["sample_dir"]), "sha256": hashlib.sha256(src).hexdigest(),
                  "cases": runs[-1]["runs"][0]["total"], "max_case_s": max_s,
                  "solution": str(dest_dir / f"{ident}.py")})
    (dest_dir / f"{ident}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bank", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--lanes", default="t/out/udebug/teacher-*", help="comma-separated globs of lane directories")
    ap.add_argument("--out", required=True)
    ap.add_argument("--judges", default="UVa", help="comma-separated; '' for every judge in the bank")
    ap.add_argument("--seeds", default="0,4242")
    ap.add_argument("--judge-timeout", type=float, default=300.0)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--only-new", action="store_true", help="keep problems already confirmed in --out as they are")
    ap.add_argument("--limit", type=int, default=0, help="confirm at most this many problems (0: all)")
    a = ap.parse_args(argv)
    judges = {j for j in a.judges.split(",") if j}
    bank = load_bank(Path(a.bank), judges)
    excluded: set[str] = set()
    results = scan_lanes([p for p in a.lanes.split(",") if p], excluded)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    seeds = [int(s) for s in a.seeds.split(",") if s]
    corpus = Path(a.corpus)

    index = {}
    prev = {}
    index_path = out / "INDEX.jsonl"
    if index_path.is_file():
        with index_path.open(encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                if e.get("status") == "solved" and e.get("lane") not in excluded:
                    prev[(e["judge"], e["id"])] = e      # a solution from an excluded lane is not kept on record

    todo = []
    for key, rec in bank.items():
        rs = results.get(key, [])
        accepted = [r for r in rs if r.get("accepted")]
        if a.only_new and key in prev:
            # keep a solved entry unless a new accepted sample is measured faster than the one on record
            faster = [r for r in accepted if r["sample_dir"] != prev[key].get("sample_dir")
                      and est_time(r, None) < (prev[key].get("max_case_s") or 0) - 0.001]
            if not faster:
                index[key] = prev[key]
                continue
        if not rec.get("statement"):
            index[key] = {"judge": key[0], "id": key[1], "title": rec.get("title"), "status": "no-statement",
                          "split": rec.get("split")}
            continue
        if rec.get("n_scored", 0) == 0:
            index[key] = {"judge": key[0], "id": key[1], "title": rec.get("title"), "status": "no-stored-output",
                          "split": rec.get("split")}
            continue
        if accepted:
            todo.append((key, rec, accepted))
        elif rs:
            index[key] = {"judge": key[0], "id": key[1], "title": rec.get("title"), "status": "unsolved",
                          "split": rec.get("split"), "in_bytes": rec.get("in_bytes"), "attempts": len(rs),
                          "best": best_failure(rs)}
        else:
            index[key] = {"judge": key[0], "id": key[1], "title": rec.get("title"), "status": "untried",
                          "split": rec.get("split"), "in_bytes": rec.get("in_bytes")}
    if a.limit:
        for key, rec, _ in todo[a.limit:]:
            index[key] = {"judge": key[0], "id": key[1], "title": rec.get("title"), "status": "accepted-unconfirmed",
                          "split": rec.get("split")}
        todo = todo[:a.limit]
    print(f"{len(bank)} problems in the bank; {len(todo)} accepted to confirm; "
          f"{sum(1 for e in index.values() if e['status'] == 'unsolved')} unsolved; "
          f"{sum(1 for e in index.values() if e['status'] == 'untried')} untried", flush=True)

    def one(item):
        key, rec, accepted = item
        e = confirm(key, rec, accepted, corpus, out, seeds, a.judge_timeout, prev.get(key))
        print(f"{key[0]}/{key[1]}: {e['status']}" + (f" max_case_s={e['max_case_s']}" if e["status"] == "solved" else ""),
              flush=True)
        return key, e

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        for key, e in ex.map(one, todo):
            index[key] = e

    entries = sorted(index.values(), key=lambda e: (e["judge"], int(e["id"]) if e["id"].isdigit() else 0, e["id"]))
    stale = 0
    for e in entries:                                    # a problem no longer solved leaves no program behind
        if e["status"] != "solved":
            for suffix in (".py", ".json"):
                f = out / e["judge"] / f"{e['id']}{suffix}"
                if f.is_file():
                    f.unlink()
                    stale += 1
    if stale:
        print(f"removed {stale} stale solution files", flush=True)
    with index_path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    counts = collections.Counter(e["status"] for e in entries)
    solved = [e for e in entries if e["status"] == "solved"]
    unsolved = [e for e in entries if e["status"] in ("unsolved", "accepted-but-not-confirmed")]
    slow = [e for e in solved if (e.get("max_case_s") or 0) > 2.0]
    lines = ["# Solved: confirmed on every stored case, twice more under fixed hash seeds", "",
             f"{len(solved)} problems. `max s` is the slowest stored case's wall time on this machine; "
             f"{len(slow)} exceed 2 s and may miss an online judge's time limit.", "",
             "| judge | id | title | cases | max s | model |", "|---|---|---|---|---|---|"]
    for e in solved:
        lines.append(f"| {e['judge']} | {e['id']} | {(e.get('title') or '').replace('|', '/')} | {e.get('cases')} | "
                     f"{e.get('max_case_s')} | {e.get('model', '')} |")
    (out / "SOLVED.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    lines = ["# Unsolved: no program reproduces every stored case yet", "",
             f"{len(unsolved)} problems with an attempt; {counts.get('untried', 0)} untried; "
             f"{counts.get('no-statement', 0)} without a statement; {counts.get('no-stored-output', 0)} without a stored output.",
             "", "| judge | id | title | attempts | best status | case | first difference |", "|---|---|---|---|---|---|---|"]
    for e in unsolved:
        b = e.get("best") or {}
        fd = (b.get("first_difference") or "").replace("|", "/").replace("\n", " ")[:120]
        lines.append(f"| {e['judge']} | {e['id']} | {(e.get('title') or '').replace('|', '/')} | {e.get('attempts', '')} | "
                     f"{b.get('status', e['status'])} | {b.get('case') or ''} | {fd} |")
    (out / "UNSOLVED.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "README.md").write_text(
        "# uDebug solutions\n\n" + __doc__.split("\n\n", 1)[1].split("\n\nA problem without")[0] + "\n\n"
        + "Counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + ".\n\n"
        "`<judge>/<id>.py` is the program to submit; `<judge>/<id>.json` is its evidence; `INDEX.jsonl` has one line per "
        "problem in the bank; `SOLVED.md` and `UNSOLVED.md` are the tables.\n", encoding="utf-8")
    print(json.dumps(dict(counts), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
