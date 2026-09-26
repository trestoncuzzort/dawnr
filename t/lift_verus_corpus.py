#!/usr/bin/env python3
"""t/lift_verus_corpus.py -- lift a corpus of verified Verus files that is not a benchmark
(one file, many functions) into t: verus-lang/verus's own `examples/` and its standard
library `source/vstd/` (MIT, The Verus Contributors), 2026-09-26.

    python3 t/lift_verus_corpus.py --name verus-examples --root CHECKOUT/examples \
        --out t/out/lifted-tasks-verus-examples --split t/out/loop/split-v5.json
    python3 t/lift_verus_corpus.py --name vstd --root CHECKOUT/source/vstd --lemmas \
        --out t/out/lifted-tasks-vstd --split t/out/loop/split-v5.json

The same pipeline as t/lift_vericoding.py with the benchmark-specific steps left out:
every exec fn (and value-returning proof fn) with an ensures in every .rs file under
--root is one candidate (t/lift_verus.targets); with --lemmas, so is every proof fn with
an ensures and no result, lifted as a task whose result `ok: bool` is a token (assigned
true) and whose requires and ensures are the lemma's own -- the proof obligation is the
lemma, restated in t, and it is labelled `lemma-as-task` in trust.jsonl. A generic lemma
(`<A>`, closures) is refused `generics` by name. Trust holes are judged per function
here (a file of many functions may hold one external_body wrapper), where a vericoding
file is refused whole.

Then: render (t/lift_verus.py), lift (t/lifter.py), native equivalence in Verus
(t/lift_check_verus.py), the weak-specification probe (not for lemma tasks, whose result
is constant by construction), and the gates of t/lift_corpora.screen without a head
(these corpora carry no problem statements): t surface notation, held-out/dev ids under
every alias, the behavioural twin on drawn inputs. No MBPP-, HumanEval- or APPS-derived
Verus data (AutoVerus, Verus-Bench, SAFE, AlphaVerus) is read: they collide with the
held-out pool one hop removed (resources note, VERIFIED-CORPORA.md).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lift_check_verus                                           # noqa: E402
import lift_corpora                                               # noqa: E402
import lift_verus                                                 # noqa: E402
import lift_vericoding                                            # noqa: E402
import loop_filter                                                # noqa: E402
import surface                                                    # noqa: E402
import twin_draws                                                 # noqa: E402

LICENSE = "MIT (The Verus Contributors)"


def stem_for(name: str, rel: Path, target: str) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", str(rel.with_suffix(""))).strip("_")
    return f"{name.replace('-', '_')}_{base}_{target}"


def source_verifies(path: Path, timeout_s: float = 600.0) -> tuple[bool, str]:
    """Run Verus on the corpus file as it stands (verus-lang/verus's examples include files
    that fail on purpose, basic_failure.rs among them). A file with any error, or one that
    does not finish, lifts nothing."""
    cmd = lift_check_verus.memory_capped([str(lift_check_verus.VERUS_BIN), "--crate-type=lib", "--output-json",
                                          str(path)])
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, cwd=path.parent)
    except subprocess.TimeoutExpired:
        return False, "verus timed out on the source file"
    m = re.search(r'"errors"\s*:\s*(\d+)', p.stdout)
    if p.returncode == 0 and m and int(m.group(1)) == 0:
        return True, ""
    first = next((ln for ln in p.stderr.splitlines() if ln.startswith("error")), f"exit {p.returncode}")
    return False, first[:200]


def canonical(task: dict) -> str:
    t = dict(task)
    t.pop("name", None)
    return json.dumps(t, sort_keys=True)


def screen(task: dict, pool, gates, gate, index, runner) -> dict:
    """lift_corpora.screen's gates for a task with no English head."""
    verdict = {"refused": None, "reason": "", "twin_check": [], "twin_of": None}
    try:
        document = surface.print_task(task).strip() + "\n"
    except surface.SurfaceError as error:
        return {**verdict, "refused": "no t notation", "reason": f"no t surface notation: {error}"}
    if not gate.admit(document, [task["name"]], []):
        return {**verdict, "refused": "gates", "reason": "held-out, listed or dev id under an alias"}
    evidence: list = []
    twin = lift_corpora.twin_of(task, index, pool, gates, runner, evidence)
    if twin is not None:
        return {**verdict, "refused": "twin", "twin_check": evidence, "twin_of": twin[0],
                "reason": f"passes every test point of gated problem {twin[0]} ({twin[1]})"}
    return {**verdict, "twin_check": evidence}


def build(args) -> dict:
    out = Path(args.out)
    meta = out.with_name(out.name + ".meta")
    root = Path(args.root)
    gates, pool, index = lift_corpora.load_gating(args.split, args.pool)
    for sub in ("staged", "sources", "sidecars", "lift", "native"):
        if (meta / sub).exists():
            shutil.rmtree(meta / sub)
    for sub in ("staged", "sources", "sidecars"):
        (meta / sub).mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    tally, refused, rendered = Counter(), [], {}
    files = sorted(root.rglob("*.rs"))
    tally["files"] = len(files)
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = f.relative_to(root)
        names = lift_verus.targets(text, lemmas=args.lemmas)
        if names and not args.crate_verified:
            ok, why = source_verifies(f)
            if not ok:
                for t in names:
                    refused.append({"file": str(rel), "target": t, "stage": "source",
                                    "reason": "the source file does not verify", "detail": why})
                    tally["source: does not verify"] += 1
                continue
        lemma_names = set(lift_verus.targets(text, lemmas=True)) - set(lift_verus.targets(text)) if args.lemmas else set()
        for t in names:
            tally["candidates"] += 1
            is_lemma = t in lemma_names
            r = lift_verus.render(text, target=t, lemma=is_lemma)
            if r.refusal:
                refused.append({"file": str(rel), "target": t, "stage": "render", "reason": r.refusal[0],
                                "detail": r.refusal[1][:200]})
                tally["render: " + r.refusal[0]] += 1
                continue
            stem = stem_for(args.name, rel, t)
            (meta / "staged" / f"{stem}.dfy").write_text(r.dafny, encoding="utf-8")
            src_copy = meta / "sources" / (re.sub(r"[^A-Za-z0-9]+", "_", str(rel.with_suffix(""))) + ".rs")
            shutil.copyfile(f, src_copy)
            rendered[stem] = {"file": str(rel), "source": f, "target": t, "lemma": is_lemma,
                              "rewrites": r.rewrites}
            tally["rendered"] += 1
    started = time.monotonic()
    summary = lift_corpora.run_lifter(meta / "staged", meta / "lift", args.jobs, args.with_check)
    lift_seconds = time.monotonic() - started
    lifted = [x for x in lift_corpora.lifted_tasks(meta / "lift") if x[0].name.split(".", 1)[0] in rendered]
    tally["lifted"] = len(lifted)

    def one(item):
        task_file, task, sidecar = item
        info = rendered[task_file.name.split(".", 1)[0]]
        return task_file.name, lift_check_verus.check(info["source"], task, sidecar.get("rename_map", {}),
                                                      meta / "native", task_file.stem, target=info["target"],
                                                      lemma=info["lemma"])
    with ThreadPoolExecutor(max(1, args.native_jobs)) as ex:
        native = dict(ex.map(one, lifted))
    (meta / "native-check.jsonl").write_text(
        "".join(json.dumps({"task": k, **v}, sort_keys=True) + "\n" for k, v in sorted(native.items())),
        encoding="utf-8")

    gate = loop_filter.TrainingDataGate(frozenset(gates.held_out | gates.dev))
    runner = twin_draws.runner(pool, lift_corpora.hung_path_for(out))
    accepted, trust, decisions = [], [], []
    seen: dict[str, str] = {}
    for task_file, task, sidecar in lifted:
        stem = task_file.name.split(".", 1)[0]
        info = rendered[stem]
        nv = native.get(task_file.name, {})
        if nv.get("verdict") != "proved":
            refused.append({"file": info["file"], "target": info["target"], "name": task["name"], "stage": "native",
                            "reason": f"equivalence to the source not proved ({nv.get('verdict')})",
                            "detail": f"{nv.get('at') or ''} {nv.get('message', '')}"[:300]})
            tally["native: " + str(nv.get("verdict"))] += 1
            continue
        tally["native: proved"] += 1
        if not info["lemma"]:
            why = lift_vericoding.weak_spec(task)
            if why:
                refused.append({"file": info["file"], "target": info["target"], "name": task["name"],
                                "stage": "weak", "reason": "weak specification", "detail": why})
                tally["weak: constant satisfies the spec"] += 1
                continue
        key = canonical(task)
        if key in seen:
            refused.append({"file": info["file"], "target": info["target"], "name": task["name"], "stage": "dedupe",
                            "reason": f"the same task as {seen[key]}"})
            tally["dedupe: the same task as another file's"] += 1
            continue
        seen[key] = task["name"]
        verdict = screen(task, pool, gates, gate, index, runner)
        if verdict["twin_check"]:
            decisions.append(lift_corpora.decision_row(task, args.name, {**verdict, "head": None}, "admitted"))
        if verdict["refused"]:
            refused.append({"file": info["file"], "target": info["target"], "name": task["name"], "stage": "gates",
                            "reason": verdict["reason"]})
            tally["gates: " + verdict["refused"]] += 1
            continue
        accepted.append((task_file, task, sidecar))
        trust.append({"name": task["name"], "task_file": task_file.name, "corpus": args.name, "file": info["file"],
                      "function": info["target"],
                      "trust": "verus-equivalence" + (", lemma-as-task" if info["lemma"] else ""),
                      "native_check": {k: nv.get(k) for k in ("verdict", "seconds", "lemmas")},
                      "lifter_check": "run" if args.with_check else "not run here (the grading machine reruns it)",
                      "render_rewrites": info["rewrites"], "kernels": "unmeasured until graded"})
    tally["accepted"] = len(accepted)
    for stale in out.glob("*.json"):
        stale.unlink()
    for task_file, task, sidecar in accepted:
        shutil.copyfile(task_file, out / task_file.name)
        shutil.copyfile(task_file.with_name(task_file.name[:-5] + ".lift.json"),
                        meta / "sidecars" / (task_file.name[:-5] + ".lift.json"))
    dump = lambda name, items: (meta / name).write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in items), encoding="utf-8")
    dump("refused.jsonl", refused)
    dump("trust.jsonl", trust)
    dump("twin-decisions.jsonl", decisions)
    dump("heads.jsonl", [])
    census = {"schema": 1, "corpus": args.name, "root": args.root_label or root.name, "license": LICENSE,
              "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "counts": dict(tally),
              "lemmas": bool(args.lemmas), "lifter_checks_run": bool(args.with_check),
              "source_verification": ("verified as one crate when Verus is built; not re-run file by file here"
                                      if args.crate_verified else "each file run through verus here; a file with "
                                      "any error lifts nothing"),
              "lifter_wall_seconds": round(lift_seconds, 1),
              "lifter_verdicts": summary.get("verdict_counts") or summary.get("verdicts"),
              "lifter_refusals": dict(lift_corpora.refusals(meta / "lift").most_common()),
              "render_refusals": dict(Counter(r["reason"] for r in refused if r["stage"] == "render").most_common()),
              "native_verdicts": dict(Counter(v.get("verdict") for v in native.values())),
              "accepted": len(accepted), "split": str(args.split), "pool": args.pool, "pool_size": len(pool)}
    (meta / "lift-census.json").write_text(json.dumps(census, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return census


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--name", required=True, help="corpus name, used in stems (verus-examples, vstd)")
    ap.add_argument("--root", required=True, help="the directory of .rs files")
    ap.add_argument("--root-label", help="how the census names the root (no machine paths in a public census)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--pool", default="v5")
    ap.add_argument("--lemmas", action="store_true", help="also lift proof fns with no result as lemma tasks")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--native-jobs", type=int, default=2)
    ap.add_argument("--with-check", action="store_true")
    ap.add_argument("--crate-verified", action="store_true",
                    help="the files are one crate verified as a whole (vstd, when Verus is built), not "
                         "file by file; skip the per-file source run and say so in the census")
    census = build(ap.parse_args(argv))
    print(json.dumps({k: census[k] for k in ("corpus", "counts", "native_verdicts", "accepted")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
