#!/usr/bin/env python3
"""E3 data: build the three training arms directly from the graded MBPP answer sets.

For each (answer-set, task): is the program well-formed, do its tests pass, and how many of the seven
kernels ACCEPT it (cell == "verified / refuted": clean verified AND twin refuted)? From that:
  raw   = tests pass and well-formed (no proof requirement)
  k<K>  = raw AND at least K kernels accept       (graded k-of-7)
  all7  = raw AND all seven kernels accept        (all-seven-verified)
Emits SFT rows (prompt, chosen) per arm, de-duplicated by (task, chosen), and prints the size/diversity
so the arms can be matched by subsampling. MBPP train pool — disjoint from the Vericoding eval.

    python3 -I e3_build_arms.py <spec-experiment-dir> <out-dir>
"""
import json, re, sys, pathlib, collections

CELL_OK = "verified / refuted"


def parse_kernels_md(path):
    """task_name -> number of the seven kernels whose cell is 'verified / refuted'."""
    out = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("task", "") or set(cells[0]) <= {"-"}:
            continue
        name = cells[0]
        kcols = cells[1:8]
        if len(kcols) < 7:
            continue
        out[name] = sum(1 for c in kcols if c == CELL_OK)
    return out


def main():
    root = pathlib.Path(sys.argv[1])
    outdir = pathlib.Path(sys.argv[2]); outdir.mkdir(parents=True, exist_ok=True)
    sets = sorted(d for d in root.iterdir() if d.is_dir() and d.name.startswith("deepseek-v3.2-"))
    cands = []  # each: {task, set, tests_pass, wellformed, kacc, prompt, chosen}
    for d in sets:
        try:
            tests = json.load(open(d / "tests.json"))
            extract = json.load(open(d / "extract.json"))
        except Exception:
            continue
        kmd = parse_kernels_md(d / "kernels.md")
        # tests keyed by name; extract keyed by task_id
        test_by_name = {v.get("name"): (v.get("overall") == "pass") for v in tests.values()} if isinstance(tests, dict) else {}
        for ekey, e in (extract.items() if isinstance(extract, dict) else []):
            tid = e.get("task_id"); fn = e.get("fn")
            name = f"mbpp_{tid}__{fn}"
            wellformed = e.get("stage") != "parse"  # a parse-stage record is a parse failure
            raw_path = d / "raw" / f"{tid}.json"
            if not raw_path.is_file():
                continue
            try:
                rec = json.load(open(raw_path))
            except Exception:
                continue
            chosen = rec.get("reply", "")
            msgs = rec.get("messages", [])
            prompt = msgs if msgs else [{"role": "user", "content": name}]
            cands.append({"task": name, "set": d.name,
                          "tests_pass": bool(test_by_name.get(name, False)),
                          "wellformed": bool(wellformed),
                          "kacc": int(kmd.get(name, 0)),
                          "prompt": prompt, "chosen": chosen})
    # distribution over tests-passing well-formed candidates
    usable = [c for c in cands if c["tests_pass"] and c["wellformed"] and c["chosen"].strip()]
    kdist = collections.Counter(c["kacc"] for c in usable)
    print(f"answer sets: {len(sets)}; candidates: {len(cands)}; tests-pass+wellformed+nonempty: {len(usable)}")
    print("kernels-accepting distribution over usable:", dict(sorted(kdist.items())))
    print("distinct tasks over usable:", len({c['task'] for c in usable}))

    def emit(name, rows):
        # de-dup by (task, chosen); keep provenance
        seen = set(); out = []
        for c in rows:
            key = (c["task"], c["chosen"])
            if key in seen:
                continue
            seen.add(key)
            out.append({"prompt": c["prompt"], "chosen": c["chosen"], "task": c["task"],
                        "set": c["set"], "kacc": c["kacc"], "arm": name})
        (outdir / f"arm-{name}.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in out), encoding="utf-8")
        print(f"  arm {name}: {len(out)} rows, {len({r['task'] for r in out})} distinct tasks")
        return out

    print("arms (before budget-matching):")
    raw = emit("raw", usable)
    emit("graded-k4", [c for c in usable if c["kacc"] >= 4])
    emit("all7", [c for c in usable if c["kacc"] >= 7])
    # also expose the k-distinct raw for reference
    return 0


if __name__ == "__main__":
    sys.exit(main())
