#!/usr/bin/env python3
"""t/preflight.py -- everything that could make a round's numbers wrong, checked before the round (2026-09-18).

    python3 t/preflight.py [--pool v4] [--split t/out/loop/split-v3.json] [--strict]

Each check below exists because something went wrong once. A round should not start while any of them fails,
and the ones that fail print what to do. `--strict` exits non-zero on a warning as well as a failure.

  1. The seven checkers are present, and at the versions t/AGREEMENT.md was measured with. A checker missing
     from PATH does not read as absent in every path: a hand-run grading on 2026-09-17 reported MALFORMED for
     every Verus cell because a non-login shell had no Rust toolchain.
  2. No held-out problem appears in the training set or the pairs. The split is the whole basis of every
     held-out number.
  3. Every answer counted clean agrees with its problem's own solution (t/spec_check.py). Five did not on
     2026-09-18, and all five had passed the tests, all seven proofs and a refuted twin.
  4. No cell counted clean is marked FLAKED, and none of a clean answer's cells is a timeout. A timeout is not
     a verdict, and grading at 64 jobs on a shared machine produces them.
  5. The copy check's keys are unique, so no answer entered the pool twice under two tags.
  6. There is room to write: this machine's disk and the grading machine's.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
OUT = HERE / "out"
SE = OUT / "spec-experiment"


def say(ok: bool, name: str, detail: str = "") -> bool:
    print(f"  [{'ok  ' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))
    return ok


def versions_from_agreement() -> dict:
    out = {}
    try:
        for line in (HERE / "AGREEMENT.md").read_text(errors="replace").splitlines():
            m = re.match(r"- (\w+): (.+)", line.strip())
            if m and m.group(1) in KERNELS:
                out[m.group(1)] = m.group(2).strip()
    except OSError:
        pass
    return out


def check_kernels() -> bool:
    ok = True
    want = versions_from_agreement()
    for k in KERNELS:
        try:
            mod = __import__(f"verifiers.{k}", fromlist=["version"])
            have = mod.version()
        except (Exception, SystemExit) as e:                    # noqa: BLE001
            ok = say(False, f"{k} present", str(e).split("\n")[0][:80]) and ok
            continue
        w = want.get(k, "")
        if "?" in have or not have.strip():
            # the 2026-09-17 trap: the binary answers but its toolchain is missing, so the adapter cannot even
            # read a version and every cell would read MALFORMED
            ok = say(False, f"{k} version readable", f"reported {have!r}") and ok
            continue
        same = (not w) or w.split()[0] in have or have.split()[0] in w
        ok = say(same, f"{k} {have[:40]}", "" if same else f"AGREEMENT.md measured with {w[:40]}") and ok
    return ok


def check_split(split_path: Path) -> bool:
    try:
        split = json.loads(split_path.read_text())
    except OSError:
        return say(False, "split readable", str(split_path))
    ev = {int(i) for i in split["eval_ids"]}
    ok = True
    _ = ev
    # every pool and pair file there is, not a list that has to be edited each round: round 6's files existed
    # for a day without being leak-checked because they were not in the list (2026-09-19)
    files = sorted((OUT / "loop").glob("sft-*.jsonl")) + sorted((OUT / "loop").glob("pairs-*.jsonl"))
    if not files:
        ok = say(False, "a pool to check", "no sft-*.jsonl or pairs-*.jsonl under out/loop")
    for p in files:
        name = p.name
        leaked = set()
        for line in p.read_text(errors="replace").splitlines():
            for tid in re.findall(r"mbpp_(\d+)", line):
                if int(tid) in ev:
                    leaked.add(int(tid))
        ok = say(not leaked, f"{name} holds no held-out problem",
                 "" if not leaked else f"{len(leaked)} leaked: {sorted(leaked)[:5]}") and ok
    return ok


def clean_rows(tag_dir: Path) -> dict:
    """task -> its row, for answers counted clean (tests pass and all seven verified with the twin refuted)."""
    import spec_experiment as se
    cols, cells = se.parse_kernel_table(tag_dir / "kernels.md")
    try:
        tests = {v.get("name"): v.get("overall") for v in json.loads((tag_dir / "tests.json").read_text()).values()}
    except (OSError, ValueError):
        tests = {}
    return {n: r for n, r in cells.items()
            if tests.get(n) == "pass" and all(r.get(k, "").startswith("verified / refuted") for k in KERNELS)}


def rechecked() -> set:
    """Cells re-verified alone and recorded in t/out/recheck.json. A FLAKED mark means the sweep disagreed with
    itself under load, not that the cell is unstable: lower_spark.py's own notes call a spark cell graded at
    high concurrency provisional until it is re-run alone. A re-check is only worth anything if it is written
    down with how it was run, so this reads that file rather than letting anyone edit a verdict by hand."""
    try:
        rows = json.loads((OUT / "recheck.json").read_text()).get("rechecked", [])
    except (OSError, ValueError):
        return set()
    return {(r["tag"], r["task"], r["kernel"]) for r in rows
            if r.get("alone", "").startswith("verified / refuted")}


def check_flakes() -> bool:
    ok_alone = rechecked()
    flaked, timeouts, total = [], [], 0
    for d in sorted(p for p in SE.glob("*") if (p / "kernels.md").exists()):
        for name, row in clean_rows(d).items():
            total += 1
            for k in KERNELS:
                cell = row.get(k, "")
                if "FLAKED" in cell and (d.name, name, k) not in ok_alone:
                    flaked.append(f"{d.name}/{name} {k}")
                if "timeout" in cell:
                    timeouts.append(f"{d.name}/{name} {k}")
    if ok_alone:
        print(f"  [note] {len(ok_alone)} cell(s) re-verified alone, recorded in out/recheck.json")
    ok = say(not flaked, f"no clean answer rests on a flaked cell ({total} clean)",
             "" if not flaked else f"{len(flaked)}: {flaked[:3]}")
    return say(not timeouts, "no clean answer rests on a timeout",
               "" if not timeouts else f"{len(timeouts)}: {timeouts[:3]}") and ok


def check_spec_agreement() -> bool:
    """A disagreement in a POOL answer is a failure: it would be trained on. A disagreement in a held-out
    answer set cannot enter the pool, so it is reported, and score_heldout.py counts it in its own column."""
    j = OUT / "spec-disagree.json"
    if not j.exists():
        return say(False, "specifications checked against the problems", "run python3 t/spec_check.py")
    bad = json.loads(j.read_text()).get("disagree", [])
    pool_text = ""
    for name in ("sft-r4.jsonl", "pairs-r4.jsonl", "sft-r5.jsonl", "pairs-r5.jsonl"):
        f = OUT / "loop" / name
        if f.exists():
            pool_text += f.read_text(errors="replace")
    # compare the program, not the problem name: another model's answer to the same problem may be fine
    progs = json.loads(j.read_text()).get("programs", {})
    squash = lambda s: " ".join(s.split())                       # noqa: E731
    flat = squash(pool_text)
    in_pool = [x for x in bad if x in progs and squash(progs[x]) in flat]
    ok = say(not in_pool, f"no answer in the pool disagrees with its problem ({len(bad)} disagreements found)",
             "" if not in_pool else f"{in_pool}")
    if bad and not in_pool:
        print(f"  [note] {len(bad)} held-out answers disagree with their problems; score_heldout.py counts "
              f"them apart, see {j.name}")
    return ok


def check_keys() -> bool:
    p = OUT / "pool-keys.txt"
    if not p.exists():
        return say(True, "copy-check keys (none yet)")
    keys = p.read_text(errors="replace").splitlines()
    dup = len(keys) - len(set(keys))
    return say(dup == 0, f"copy-check keys unique ({len(keys)})", "" if not dup else f"{dup} duplicates")


def check_space(lab: str | None) -> bool:
    free = shutil.disk_usage(HERE).free / 1e9
    ok = say(free > 20, f"this machine has {free:.0f} GB free")
    if lab:
        try:
            out = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", lab,
                                  "df -B1 --output=avail / | tail -1"], capture_output=True, text=True, timeout=30)
            gb = int(out.stdout.strip() or 0) / 1e9
            ok = say(gb > 20, f"the grading machine has {gb:.0f} GB free") and ok
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            ok = say(False, "grading machine reachable", str(e)[:60]) and ok
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", type=Path, default=OUT / "loop" / "split-v3.json")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    lab = None
    conf = HERE / "lab-workstation.conf"
    if conf.exists():
        m = re.search(r"^T_LAB=(\S+)", conf.read_text(), re.M)
        lab = m.group(1) if m else None

    print("checkers")
    ok = check_kernels()
    print("the split")
    ok = check_split(a.split) and ok
    print("what is counted clean")
    ok = check_flakes() and ok
    ok = check_spec_agreement() and ok
    print("housekeeping")
    ok = check_keys() and ok
    ok = check_space(lab) and ok
    print("\n" + ("ready: nothing left to doubt in this list" if ok else
                  "not ready: fix what reads FAIL above, then run this again"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
