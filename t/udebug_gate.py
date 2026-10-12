#!/usr/bin/env python3
"""t/udebug_gate.py -- grade teacher samples on judge problems and keep what the oracle accepts (2026-10-12).

    python3 t/udebug_gate.py --samples t/out/udebug/teacher-<tag> --corpus t/out/udebug-bulk-20261011 \\
        --bank t/out/udebug/bank.jsonl --kernels dafny --jobs 4

Two oracles, in the cheap order. For every sample `<judge>-<id>/s<k>/p<id>.t` with its io module:
  1. judge   `t/judge.py` runs the task's Dafny lowering (Python backend, unbounded ints) on every
             stored case; PASS only when every case with a stored output is reproduced. A FAIL is
             an execution refutation, which is cheaper than a proof and refutes the spec as well as
             the body (FVAPPS, arXiv:2502.05714, found tests and specifications disagreeing).
  2. verify  `t/cli.py verify --json` on the judge-passers (every sample with --verify-all): a kernel
             counts when its verdict says COUNTS, the real program verified and the twin refuted.
A sample is ACCEPTED when the judge passes and at least --min-kernels kernels count.

Rows (ReST-EM's M-step input, arXiv:2312.06585, capped per problem as that paper capped at 10):
  statement-given   prompt: the student system text + the statement, the stored sample case and
                    the ask; chosen: the accepted task re-printed by surface's printer (whitespace
                    and comments the parser accepts are not something to train on, as
                    t/loop_dataset.py says). The io module rides along in `io_module`, not trained.
  spec-given        t/student_rows.row_for: the header/spec given, the body asked.
  judge-pair        chosen: an accepted sample; rejected: a sample of the same problem that parsed
                    and FAILED the judge at a stored case (not a timeout, not a parse error): a
                    negative the judge itself refuted, written beside the twin negatives
                    t/loop_dataset.py builds.
Rows are built only for problems the bank marks split=train and not hand_solved. Everything else
is reported, nothing dropped silently: report.json and report.md beside --samples.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import loop_dataset      # noqa: E402  (fence)
import spec_experiment   # noqa: E402  (STUDENT_SYSTEM)
import student_rows      # noqa: E402  (row_for)
import surface           # noqa: E402  (parse_file, print_task)

JUDGE_LINE = re.compile(r"^(\d+)/(\d+) test files match the judge's output(?: \((\d+) without a stored output\))?")
STUDENT_ASK = ("Write the t task `p{id}` for this judge problem: its requires and ensures state the problem as "
               "the statement defines it and its body solves it. The task sees one case at a time; its parameters "
               "are the numbers (or sequences of ints) of one case and its result is one int, bool or seq.\n\n")


def run(cmd: list[str], timeout: float, cwd: Path) -> tuple[int | None, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        return None, (e.stdout or "" if isinstance(e.stdout, str) else "") + "\n[timeout]"


def judge(task: Path, io: Path, tests: Path, timeout: float) -> dict:
    rc, out = run([sys.executable, str(HERE / "judge.py"), str(task), "--tests", str(tests), "--io", str(io),
                   "--show"], timeout, HERE.parent)
    if rc is None:
        return {"status": "timeout", "rc": None}
    m = next((JUDGE_LINE.match(line) for line in out.splitlines() if JUDGE_LINE.match(line)), None)
    if m is None:
        return {"status": "error", "rc": rc, "tail": out[-1500:]}
    passed, total, skipped = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    first = next((line.strip() for line in out.splitlines() if line.strip().startswith("line ")), None)
    if first is not None and len(first) > 240:          # a differing line can be a thousand-digit number
        first = first[:240] + f"...[{len(first) - 240} more]"
    return {"status": "pass" if rc == 0 and passed == total else "fail", "rc": rc,
            "passed": passed, "total": total, "skipped": skipped, "first_difference": first}


def verify(task: Path, kernels: str, timeout: float) -> dict:
    cmd = [sys.executable, str(HERE / "cli.py"), "verify", str(task), "--json"]
    if kernels:
        cmd += ["--kernels", kernels]
    rc, out = run(cmd, timeout, HERE.parent)
    if rc is None:
        return {"status": "timeout", "kernels": {}}
    verdicts = {}
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("severity") == "verdict":
            verdicts[d.get("kernel") or "-"] = d.get("message", "")
    counted = sorted(k for k, m in verdicts.items() if k != "-" and m.startswith("COUNTS"))
    return {"status": "ran", "rc": rc, "kernels": verdicts, "counted": counted}


def grade_one(d: Path, corpus: Path, kernels: str, judge_timeout: float, verify_timeout: float,
              verify_all: bool, min_kernels: int) -> dict:
    rec = json.loads((d / "record.json").read_text(encoding="utf-8"))
    ident = rec["id"]
    res = {"judge_name": rec["judge"], "id": ident, "k": rec["sample_index"], "dir": str(d),
           "fences": rec.get("fences", {}), "parse": None, "judge": None, "verify": None, "accepted": False}
    task_path, io_path = d / f"p{ident}.t", d / f"p{ident}_io.py"
    if not (task_path.is_file() and io_path.is_file()):
        res["parse"] = "no-fences"
        return finish(d, res)
    try:
        surface.parse_file(str(task_path))
        res["parse"] = "ok"
    except Exception as e:                                   # the parser's own error is the record
        res["parse"] = f"error: {str(e)[:300]}"
        return finish(d, res)
    res["judge"] = judge(task_path, io_path, corpus / rec["tests_dir"], judge_timeout)
    if res["judge"]["status"] == "pass" or verify_all:
        res["verify"] = verify(task_path, kernels, verify_timeout)
    res["accepted"] = (res["judge"]["status"] == "pass" and res["verify"] is not None
                       and len(res["verify"].get("counted", [])) >= min_kernels)
    return finish(d, res)


def finish(d: Path, res: dict) -> dict:
    (d / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    return res


def load_bank(path: Path) -> dict[str, dict]:
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[f"{r['judge']}/{r['id']}"] = r
    return out


def build_rows(results: list[dict], bank: dict[str, dict], cap: int, pair_cap: int) -> tuple[list[dict], list[dict], dict]:
    by_problem: dict[str, list[dict]] = {}
    for r in results:
        by_problem.setdefault(f"{r['judge_name']}/{r['id']}", []).append(r)
    rows, pairs = [], []
    skipped = {"not-train": 0, "hand-solved": 0, "duplicate-chosen": 0, "over-cap": 0}
    for key, rs in sorted(by_problem.items()):
        b = bank.get(key, {})
        if b.get("hand_solved"):
            skipped["hand-solved"] += sum(r["accepted"] for r in rs)
            continue
        if b.get("split") != "train":
            skipped["not-train"] += sum(r["accepted"] for r in rs)
            continue
        chosen_texts, chosen = set(), []
        for r in rs:
            if not r["accepted"]:
                continue
            d = Path(r["dir"])
            task = surface.parse_file(str(d / f"p{r['id']}.t"))
            text = surface.print_task(task).strip()
            if text in chosen_texts:
                skipped["duplicate-chosen"] += 1
                continue
            chosen_texts.add(text)
            if len(chosen) >= cap:
                skipped["over-cap"] += 1
                continue
            rec = json.loads((d / "record.json").read_text(encoding="utf-8"))
            chosen.append((r, task, text, rec, (d / f"p{r['id']}_io.py").read_text(encoding="utf-8")))
        rejected_texts, rejected = set(), []
        for r in rs:
            if r["parse"] != "ok" or not r["judge"] or r["judge"]["status"] != "fail":
                continue
            d = Path(r["dir"])
            text = surface.print_task(surface.parse_file(str(d / f"p{r['id']}.t"))).strip()
            if text in rejected_texts or text in chosen_texts:
                continue
            rejected_texts.add(text)
            rejected.append((r, text))
        for r, task, text, rec, io_module in chosen:
            user = rec["messages"][-1]["content"]
            user = user[:user.rfind("Write the t task")] + STUDENT_ASK.format(id=r["id"]).strip()
            prompt = [{"role": "system", "content": spec_experiment.STUDENT_SYSTEM}, {"role": "user", "content": user}]
            base = {"name": f"p{r['id']}", "source": "udebug-teacher", "problem": key, "sample": r["k"],
                    "counted_kernels": r["verify"]["counted"], "judge_files": r["judge"]["total"]}
            rows.append(dict(base, kind="statement-given", prompt=prompt, chosen=loop_dataset.fence(text),
                             io_module=io_module))
            rows.append(dict(student_rows.row_for(task), **base, kind="spec-given"))
            for rr, rtext in rejected[:pair_cap]:
                pairs.append(dict(base, kind="judge-pair", prompt=prompt, chosen=loop_dataset.fence(text),
                                  rejected=loop_dataset.fence(rtext), rejected_sample=rr["k"],
                                  rejected_reason=f"judge {rr['judge']['passed']}/{rr['judge']['total']}: "
                                                  f"{rr['judge'].get('first_difference')}"))
    return rows, pairs, skipped


def report(results: list[dict], rows: list[dict], pairs: list[dict], skipped: dict, out: Path, kernels: str):
    n = len(results)
    problems = {f"{r['judge_name']}/{r['id']}" for r in results}
    js = [r["judge"]["status"] if r["judge"] else "not-run" for r in results]
    counted: dict[str, int] = {}
    for r in results:
        for k in (r["verify"] or {}).get("counted", []):
            counted[k] = counted.get(k, 0) + 1
    accepted_problems = {f"{r['judge_name']}/{r['id']}" for r in results if r["accepted"]}
    summary = {"samples": n, "problems": len(problems), "kernels_requested": kernels or "all present",
               "fences_both": sum(1 for r in results if r["parse"] != "no-fences"),
               "parsed": sum(1 for r in results if r["parse"] == "ok"),
               "judge": {s: js.count(s) for s in sorted(set(js))},
               "verified_counted_by_kernel": counted,
               "accepted_samples": sum(1 for r in results if r["accepted"]),
               "accepted_problems": len(accepted_problems),
               "rows": {"statement-given": sum(1 for x in rows if x["kind"] == "statement-given"),
                        "spec-given": sum(1 for x in rows if x["kind"] == "spec-given"), "judge-pair": len(pairs)},
               "rows_skipped": skipped}
    (out / "report.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# uDebug gate report", "", "```", json.dumps(summary, indent=1), "```", "",
             "| problem | k | parse | judge | counted kernels | accepted |", "|---|---|---|---|---|---|"]
    for r in sorted(results, key=lambda r: (r["judge_name"], int(r["id"]) if r["id"].isdigit() else 0, r["id"], r["k"])):
        j = r["judge"]
        jtxt = "-" if not j else (f"{j['status']} {j.get('passed', '')}/{j.get('total', '')}"
                                  + (f" ({j.get('skipped')} unstored)" if j.get("skipped") else ""))
        v = ", ".join((r["verify"] or {}).get("counted", [])) or ("-" if not r["verify"] else "none")
        lines.append(f"| {r['judge_name']}/{r['id']} | {r['k']} | {r['parse']} | {jtxt} | {v} | "
                     f"{'yes' if r['accepted'] else ''} |")
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--samples", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--kernels", default="dafny", help="comma-separated; '' for every present kernel")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--judge-timeout", type=float, default=900.0)
    ap.add_argument("--verify-timeout", type=float, default=1800.0)
    ap.add_argument("--verify-all", action="store_true", help="verify judge failures too")
    ap.add_argument("--min-kernels", type=int, default=1)
    ap.add_argument("--cap", type=int, default=4, help="accepted samples kept per problem")
    ap.add_argument("--pair-cap", type=int, default=4)
    ap.add_argument("--regrade", action="store_true", help="ignore existing result.json files")
    a = ap.parse_args(argv)
    samples, corpus = Path(a.samples), Path(a.corpus)
    dirs = sorted(p.parent for p in samples.glob("*/s*/record.json"))
    todo = [d for d in dirs if a.regrade or not (d / "result.json").is_file()]
    print(f"{len(dirs)} samples, {len(todo)} to grade", flush=True)

    def one(d: Path) -> dict:
        r = grade_one(d, corpus, a.kernels, a.judge_timeout, a.verify_timeout, a.verify_all, a.min_kernels)
        j = r["judge"]["status"] if r["judge"] else "-"
        print(f"{r['judge_name']}/{r['id']} s{r['k']}: parse={r['parse']} judge={j} "
              f"counted={(r['verify'] or {}).get('counted', [])} accepted={r['accepted']}", flush=True)
        return r

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        list(ex.map(one, todo))
    results = [json.loads((d / "result.json").read_text(encoding="utf-8")) for d in dirs]
    rows, pairs, skipped = build_rows(results, load_bank(Path(a.bank)), a.cap, a.pair_cap)
    with (samples / "rows.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (samples / "pairs.jsonl").open("w", encoding="utf-8") as f:
        for r in pairs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    report(results, rows, pairs, skipped, samples, a.kernels)
    return 0


if __name__ == "__main__":
    sys.exit(main())
