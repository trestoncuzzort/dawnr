#!/usr/bin/env python3
"""review_triage.py: run every reviewer-proposed failing test against the current code, one file per finding.

    python3 t/review_triage.py --review t/out/review-20261013 [--module t/answer.py] [--jobs 4]

A finding whose test fails is REPRODUCED (the claim stands on today's code, so a human fixes it with that very test);
one whose test passes is NOT-REPRODUCED (the code already does what the test asks, or the claim was wrong); one
whose test cannot even run is ERROR (an import the machine lacks, a fixture the reviewer imagined). Results go to
<review>/REPRO.jsonl, one line per finding, and the test files stay under <review>/repro/ for the fix. Nothing
here changes the modules; it only sorts the claims by whether the code refutes them.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = '''import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "t"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "locallm"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import pytest
'''


def normalize(test: str) -> str:
    """The reviewer wrote `from t import x` or `from t.x import y`; the modules import flat from t/."""
    test = re.sub(r"^(\s*)from t import (\w+)( as \w+)?", r"\1import \2\3", test, flags=re.M)
    test = re.sub(r"^(\s*)from t\.(\w+) import", r"\1from \2 import", test, flags=re.M)
    test = re.sub(r"^(\s*)import t\.(\w+) as (\w+)", r"\1import \2 as \3", test, flags=re.M)
    test = re.sub(r"\bt\.(\w+)\.", r"\1.", test) if re.search(r"^\s*import t\b", test, re.M) is None else test
    return test


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--review", required=True)
    ap.add_argument("--module", default="", help="only this module's findings")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--pytest", default=str(Path.home() / ".local/share/t-proof-venv/bin/pytest"))
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args(argv)
    review = Path(a.review)
    repro = review / "repro"
    repro.mkdir(exist_ok=True)
    done = set()
    out_path = review / "REPRO.jsonl"
    if out_path.is_file():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["module"], r["index"]))
    jobs = []
    for p in sorted(glob.glob(str(review / "*.json"))):
        if p.endswith("SUMMARY.json"):
            continue
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        if a.module and d["module"] != a.module:
            continue
        for i, f in enumerate(d["findings"]):
            if "error" in f or not isinstance(f.get("test"), str) or not f["test"].strip():
                continue
            if (d["module"], i) in done:
                continue
            jobs.append((d["module"], i, f))
    print(f"{len(jobs)} findings to run", flush=True)

    def one(job):
        module, i, f = job
        stem = module.replace("/", "__").replace(".py", "") + f"__{i}"
        test_file = repro / f"test_{stem}.py"
        body = normalize(f["test"])
        test_file.write_text(HEADER + "\n" + body + "\n", encoding="utf-8")
        try:
            p = subprocess.run([a.pytest, "-q", "-p", "no:cacheprovider", "-x", str(test_file)], cwd=str(ROOT / "t"),
                               capture_output=True, text=True, timeout=a.timeout)
            tail = (p.stdout + p.stderr)[-1500:]
            if p.returncode == 0:
                verdict = "not-reproduced"
            elif "failed" in p.stdout and ("passed" in p.stdout or "failed" in p.stdout.splitlines()[-1]) and "error" not in p.stdout.splitlines()[-1]:
                verdict = "reproduced"
            else:
                verdict = "error"
            if verdict == "error" and re.search(r"\b\d+ failed\b", p.stdout) and not re.search(r"\b\d+ errors?\b", p.stdout):
                verdict = "reproduced"
        except subprocess.TimeoutExpired:
            verdict, tail = "error", "timeout"
        rec = {"module": module, "index": i, "line": f.get("line"), "severity": f.get("severity"),
               "confidence": f.get("confidence"), "claim": f.get("claim"), "verdict": verdict, "test_file": str(test_file),
               "tail": tail[-600:]}
        print(f"{verdict:>14}  {f.get('severity', '?'):>8}  {module}:{f.get('line')}  {str(f.get('claim'))[:80]}", flush=True)
        return rec

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex, out_path.open("a", encoding="utf-8") as out:
        for rec in ex.map(one, jobs):
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
    counts = {}
    for line in out_path.read_text(encoding="utf-8").splitlines():
        v = json.loads(line)["verdict"]
        counts[v] = counts.get(v, 0) + 1
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
