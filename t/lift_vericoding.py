#!/usr/bin/env python3
"""t/lift_vericoding.py -- lift vericoding-benchmark's verified Verus and Lean solutions
into t, through the same gates as the Dafny track (2026-09-26).

    python3 t/lift_vericoding.py --language verus --vericoding DIR \
        --out t/out/lifted-tasks-vericoding-verus --split t/out/loop/split-v5.json \
        --dedupe-against t/out/lifted-tasks-2026-09-26 [--dedupe-against ...] [--jobs 2]

The Dafny track (`t/lift_corpora.py`, t/LIFT-2026-09-26.md) lifted vericoding's
`vericoded/D*` files. This does the same for `vericoded/V*_vericoded.rs` (962 Verus
solutions) and `vericoded/L*_vericoded.lean` (626 Lean solutions): the verified
solutions, each a program with its specification. `specs/` holds the specifications
alone (with files that do not compile, by the benchmark's own README) and is read only
to check that a solution did not change its specification.

Per file, in order, each step a refusal by name (refused.jsonl, stage and reason):

  select   a file whose task the benchmark lists as an issue (jsonl/<lang>_issues.jsonl),
           that its manual inspection found mistranslated or weak
           (inspection/MISTRANSLATED.md, WEAK.md), whose specification differs from
           specs/<ID>_specs.* (the vericoder changed what it was asked to prove), or
           whose problem is already lifted: vericoding names every task's source and
           source id (vericoding_benchmark_v1.csv), and a problem another lift already
           holds -- the Dafny track, or the Verus track for the Lean one -- is skipped,
           as is a second member of one of the benchmark's near-duplicate groups.
  render   the language front end (t/lift_verus.py, t/lift_lean.py) refuses what t
           cannot express, by name, or renders Dafny.
  lift     t/lifter.py, unchanged: resolve, parse, classify, rewrite (and, with
           --with-check, its Dafny equivalence lemmas and differential run).
  native   the lifted contract is proved equivalent to the SOURCE contract in the
           source's own prover (t/lift_check_verus.py, t/lift_check_lean.py). A task
           whose equivalence is not proved is refused: its English head describes the
           source problem, and nothing else ties the lifted spec to it.
  weak     a specification that a constant result satisfies on every admissible input
           the t interpreter draws (the benchmark's WEAK.md failure mode, e.g. a
           postcondition `result >= 0` for a counting problem) is refused.
  gates    lift_corpora.screen, unchanged: the held-out ids under every alias and the
           same-task exclusions, the dev split, a HumanEval index that names a gated
           problem (Clever's numbering is HumanEval's), and the behavioural twin on drawn
           inputs.

Outputs mirror t/lift_corpora.py: --out holds the accepted task JSON; <out>.meta holds
staged/ (the rendered .dfy), sources/ (the vericoded files lifted), sidecars/, heads.jsonl,
refused.jsonl, twin-decisions.jsonl, native-check.jsonl (every lifted task's equivalence
verdict), trust.jsonl (each accepted task's trust record) and lift-census.json.
Grading in seven kernels is the queue step `bash t/r12_data_queue.sh lift-vericoding-<lang>`.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import interp                                                     # noqa: E402
import lift_check_lean                                            # noqa: E402
import lift_check_verus                                           # noqa: E402
import lift_corpora                                               # noqa: E402
import lift_lean                                                  # noqa: E402
import lift_verus                                                 # noqa: E402
import loop_filter                                                # noqa: E402
import twin_draws                                                 # noqa: E402

LANGS = {"verus": {"prefix": "V", "ext": ".rs", "front": lift_verus},
         "lean": {"prefix": "L", "ext": ".lean", "front": lift_lean}}
LICENSE = "MIT (Beneficial AI Foundation, 2025)"
TRUST_NATIVE = {"verus": "verus-equivalence", "lean": "lean-equivalence"}


# ------------------------------------------------------------ benchmark --

def benchmark_rows(src: Path) -> dict[str, dict]:
    with open(src / "vericoding_benchmark_v1.csv", encoding="utf-8") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


def task_rows(src: Path, lang: str) -> dict[str, dict]:
    rows = {}
    for line in (src / "jsonl" / f"{lang}_tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["id"]] = r
    return rows


def issue_ids(src: Path, lang: str) -> dict[str, str]:
    out = {}
    path = src / "jsonl" / f"{lang}_issues.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["id"]] = r.get("qa-issue-type") or "issue"
    return out


def inspection_ids(src: Path) -> dict[str, str]:
    """Ids the benchmark's manual inspection classified mistranslated or weak."""
    out = {}
    for name, label in (("MISTRANSLATED.md", "mistranslated"), ("WEAK.md", "weak")):
        path = src / "inspection" / name
        if path.exists():
            for vid in re.findall(r"\b([DLV][A-Z]\d{4})\b", path.read_text(encoding="utf-8")):
                out.setdefault(vid, label)
    return out


def problem_key(row: dict) -> tuple[str, str]:
    """The source problem a task comes from. HumanEval by index, whichever benchmark
    carried it (vericoding's humaneval rows, Clever's -- the same numbering, the
    benchmark README -- and HumanEval-Dafny's file names)."""
    source, sid = row.get("source", ""), row.get("source-id", "") or ""
    if source in ("humaneval", "clever") or sid.startswith(("humaneval", "clever")):
        m = re.search(r"(\d+)", sid)
        if m:
            return ("humaneval", str(int(m.group(1))))
    return (source, sid)


def lifted_keys(dirs: list[Path], rows: dict[str, dict]) -> dict[tuple, str]:
    """Problem key -> the task another lift already holds, for every task file in `dirs`."""
    out: dict[tuple, str] = {}
    for d in dirs:
        for f in sorted(d.glob("*.json")):
            stem = f.name.split(".", 1)[0]
            m = re.match(r"vericoding_([DLV][A-Z]\d{4})$", stem)
            if m and m.group(1) in rows:
                out.setdefault(problem_key(rows[m.group(1)]), f"{d.name}/{f.name}")
                continue
            m = re.match(r"humaneval_dafny_(\d+)_", stem)
            if m:
                out.setdefault(("humaneval", str(int(m.group(1)))), f"{d.name}/{f.name}")
    return out


# ------------------------------------------------- specification unchanged --

def _norm(text: str, lang: str) -> str:
    if lang == "verus":
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"//[^\n]*", "", text)
    else:
        text = re.sub(r"/-.*?-/", "", text, flags=re.S)
        text = re.sub(r"--[^\n]*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _with_preamble(secs: dict, text: str, comment: str) -> dict:
    """Some solutions (vericoding's DafnyBench-derived ones) drop the `<vc-preamble>`
    markers but keep the preamble itself: everything before `<vc-helpers>` is then the
    preamble, markers and comments aside."""
    if "vc-preamble" not in secs:
        m = re.search(re.escape(comment) + r"\s*<vc-helpers>", text)
        if m:
            secs = dict(secs)
            secs["vc-preamble"] = text[:m.start()]
    return secs


def spec_changed(solution: str, spec: str, lang: str) -> Optional[str]:
    """None when the solution states the specification it was given; else what differs.
    Verus: the preamble and the spec sections, as written (comments aside). Lean: the
    preamble, the program's signature, and the postcondition definition or the
    specification theorem's statement."""
    if lang == "verus":
        a, b = _with_preamble(lift_verus.sections(solution), solution, "//"), \
            _with_preamble(lift_verus.sections(spec), spec, "//")
        for sec in ("vc-preamble", "vc-spec"):
            if _norm(a.get(sec, ""), lang) != _norm(b.get(sec, ""), lang):
                return sec
        return None
    a, b = _with_preamble(lift_lean.sections(solution), solution, "--"), \
        _with_preamble(lift_lean.sections(spec), spec, "--")
    if _norm(a.get("vc-preamble", ""), lang) != _norm(b.get("vc-preamble", ""), lang):
        return "vc-preamble"
    try:
        fa, fb = lift_lean.parse_file(solution), lift_lean.parse_file(spec)
    except lift_lean.LeanRefusal:
        return None
    for n, d in fb.defs.items():
        if n.endswith(("_postcond", "_precond")):
            if n not in fa.defs or _norm(fa.defs[n].text, lang) != _norm(d.text, lang):
                return n
    for n, t in fb.theorems.items():
        if n not in fa.theorems or _norm(fa.theorems[n].stmt_text, lang) != _norm(t.stmt_text, lang):
            return n
    for n, d in fb.defs.items():
        if n in fa.defs and n in re.findall(r"def\s+([^\s(:{]+)", b.get("vc-definitions", "")):
            sig = lambda x: _norm(x.text.split(":=")[0], lang)
            if sig(fa.defs[n]) != sig(d):
                return f"signature of {n}"
    return None


# ------------------------------------------------------------ weak specs --

def weak_spec(task: dict, limit: int = 400) -> Optional[str]:
    """A constant that satisfies every ensures on every admissible input the t interpreter
    draws (at least three), or None. A task with no parameters has a constant answer by
    construction and is not asked."""
    if not task["params"]:
        return None
    names = [(p["name"], p["type"]) for p in task["params"]]
    funs = interp.funs_of(task, task["body"])
    ret = task["returns"][0]
    cands = {"int": [0, 1, -1], "bool": [True, False], "seq": [(), (0,)]}.get(ret["type"]
                                                                            if isinstance(ret["type"], str) else "")
    if not cands:
        return None
    admissible = []
    for env0 in interp.domain(task, names, limit):
        try:
            if all(interp.ev(c, env0, funs, interp.St()) for c in task.get("requires", [])):
                admissible.append(env0)
        except (interp.Undef, interp.Budget, RecursionError):
            continue
    if len(admissible) < 3:
        return None
    for c in cands:
        ok = True
        for env0 in admissible:
            env = dict(env0)
            env[ret["name"]] = c
            try:
                if not all(interp.ev(e, env, funs, interp.St()) for e in task["ensures"]):
                    ok = False
                    break
            except (interp.Undef, interp.Budget, RecursionError):
                ok = False
                break
        if ok:
            shown = list(c) if isinstance(c, tuple) else c
            return f"the constant {json.dumps(shown)} satisfies every ensures on all {len(admissible)} admissible drawn inputs"
    return None


# ---------------------------------------------------------------- stages --

def select(args, lang: str, rows: dict, trows: dict) -> tuple[list[tuple[str, Path]], list[dict], Counter]:
    """(files to render, refusals, counts)."""
    src = Path(args.vericoding)
    cfg = LANGS[lang]
    files = sorted((src / "vericoded").glob(f"{cfg['prefix']}*_vericoded{cfg['ext']}"))
    issues, inspected = issue_ids(src, lang), inspection_ids(src)
    already = lifted_keys([Path(d) for d in args.dedupe_against or []], rows)
    keep, refused, tally = [], [], Counter()
    groups_seen: dict[str, str] = {}
    tally["files"] = len(files)
    for f in files:
        vid = f.name.split("_", 1)[0]
        row = rows.get(vid, {})
        reason = None
        if vid in issues:
            reason = f"listed in {lang}_issues.jsonl ({issues[vid]})"
        elif vid in inspected:
            reason = f"inspection: {inspected[vid]}"
        else:
            spec_path = src / "specs" / f"{vid}_specs{cfg['ext']}"
            if not spec_path.exists():
                reason = "no specs file to compare against"
            else:
                changed = spec_changed(f.read_text(encoding="utf-8"), spec_path.read_text(encoding="utf-8"), lang)
                if changed:
                    reason = f"specification changed by the vericoder ({changed})"
        if reason is None:
            key = problem_key(row)
            if key in already:
                reason = f"already lifted: {already[key]}"
        if reason is None:
            group = row.get("qa-near-duplicate-group") or ""
            if group and group in groups_seen:
                reason = f"near-duplicate of {groups_seen[group]} (group {group})"
            elif group:
                groups_seen[group] = vid
        if reason:
            refused.append({"id": vid, "stage": "select", "reason": reason})
            tally["select: " + reason.split(" (")[0].split(":")[0]] += 1
            continue
        keep.append((vid, f))
    tally["selected"] = len(keep)
    return keep, refused, tally


def render_all(keep, lang: str, staged: Path, sources: Path) -> tuple[dict, list[dict], Counter]:
    front = LANGS[lang]["front"]
    staged.mkdir(parents=True, exist_ok=True)
    sources.mkdir(parents=True, exist_ok=True)
    rendered, refused, tally = {}, [], Counter()
    for vid, f in keep:
        r = front.render(f.read_text(encoding="utf-8"))
        if r.refusal:
            refused.append({"id": vid, "stage": "render", "reason": r.refusal[0], "detail": r.refusal[1]})
            tally["render: " + r.refusal[0]] += 1
            continue
        stem = f"vericoding_{vid}"
        (staged / f"{stem}.dfy").write_text(r.dafny, encoding="utf-8")
        shutil.copyfile(f, sources / f.name)
        rendered[stem] = {"id": vid, "source": f, "rewrites": r.rewrites, "target": r.target}
        tally["rendered"] += 1
    return rendered, refused, tally


def native_all(lang: str, lifted, rendered: dict, work: Path, jobs: int) -> dict[str, dict]:
    def one(item):
        task_file, task, sidecar = item
        stem = task_file.name.split(".", 1)[0]
        src = rendered[stem]["source"]
        if lang == "verus":
            res = lift_check_verus.check(src, task, sidecar.get("rename_map", {}), work, task_file.stem)
        else:
            res = lift_check_lean.check(src, task, work, task_file.stem)
        return task_file.name, res
    out = {}
    with ThreadPoolExecutor(max(1, jobs)) as ex:
        for name, res in ex.map(one, lifted):
            out[name] = res
    return out


def build(args) -> dict:
    lang = args.language
    out = Path(args.out)
    meta = out.with_name(out.name + ".meta")
    src = Path(args.vericoding)
    gates, pool, index = lift_corpora.load_gating(args.split, args.pool)
    rows, trows = benchmark_rows(src), task_rows(src, lang)
    for sub in ("staged", "sources", "sidecars", "lift", "native"):
        if (meta / sub).exists() and not args.resume:
            shutil.rmtree(meta / sub)
    out.mkdir(parents=True, exist_ok=True)
    (meta / "sidecars").mkdir(parents=True, exist_ok=True)

    keep, refused, tally = select(args, lang, rows, trows)
    rendered, r_ref, r_tally = render_all(keep, lang, meta / "staged", meta / "sources")
    refused += r_ref
    tally.update(r_tally)
    started = time.monotonic()
    summary = lift_corpora.run_lifter(meta / "staged", meta / "lift", args.jobs, args.with_check)
    lift_seconds = time.monotonic() - started
    lifter_refusals = lift_corpora.refusals(meta / "lift")
    for o in sorted((meta / "lift").glob("*.outcome.json")):
        rec = json.loads(o.read_text(encoding="utf-8"))
        vid = o.name.split(".", 1)[0][len("vericoding_"):]
        for key in ("resolve_refusal", "parse_refusal"):
            if rec.get(key):
                refused.append({"id": vid, "stage": "lift", "reason": f"{key.split('_')[0]}:{rec[key].get('reason')}",
                                "detail": str(rec[key].get("token"))[:200]})
        for m in rec.get("methods", []):
            if m.get("refusal"):
                refused.append({"id": vid, "stage": "lift", "reason": f"classify:{m['refusal'].get('reason')}",
                                "detail": str(m["refusal"].get("token"))[:200]})
    lifted = lift_corpora.lifted_tasks(meta / "lift")
    tally["lifted"] = len(lifted)

    native = native_all(lang, lifted, rendered, meta / "native", args.native_jobs)
    (meta / "native-check.jsonl").write_text(
        "".join(json.dumps({"task": k, **v}, sort_keys=True) + "\n" for k, v in sorted(native.items())),
        encoding="utf-8")

    gate = loop_filter.TrainingDataGate(frozenset(gates.held_out | gates.dev))
    runner = twin_draws.runner(pool, lift_corpora.hung_path_for(out))
    accepted, heads, decisions, trust = [], [], [], []
    for task_file, task, sidecar in lifted:
        stem = task_file.name.split(".", 1)[0]
        vid = stem[len("vericoding_"):]
        nv = native.get(task_file.name, {})
        if nv.get("verdict") != "proved":
            refused.append({"id": vid, "name": task["name"], "stage": "native",
                            "reason": f"equivalence to the source not proved ({nv.get('verdict')})",
                            "detail": f"{nv.get('at') or ''} {nv.get('message', '')}"[:300]})
            tally["native: " + str(nv.get("verdict"))] += 1
            continue
        tally["native: proved"] += 1
        why = weak_spec(task)
        if why:
            refused.append({"id": vid, "name": task["name"], "stage": "weak", "reason": "weak specification",
                            "detail": why})
            tally["weak: constant satisfies the spec"] += 1
            continue
        verdict = lift_corpora.screen(stem, task, trows_for_heads(trows, rows), {}, pool, gates, gate, index, runner)
        if verdict["twin_check"]:
            decisions.append(lift_corpora.decision_row(task, "vericoding", verdict, "admitted"))
        if verdict["refused"]:
            refused.append({"id": vid, "name": task["name"], "stage": "gates", "reason": verdict["reason"]})
            tally["gates: " + verdict["refused"]] += 1
            continue
        accepted.append((task_file, task, sidecar))
        if verdict["head"] is not None:
            heads.append(verdict["head"])
            tally["head: " + verdict["head"]["curation"]] += 1
        else:
            tally["no head"] += 1
        trust.append({"name": task["name"], "task_file": task_file.name, "id": vid,
                      "source": rows.get(vid, {}).get("source"), "source_id": rows.get(vid, {}).get("source-id"),
                      "language": lang, "trust": TRUST_NATIVE[lang],
                      "native_check": {k: nv.get(k) for k in ("verdict", "seconds", "lemmas")},
                      "lifter_check": "run" if args.with_check else "not run here (queue step reruns it)",
                      "render_rewrites": rendered[stem]["rewrites"],
                      "kernels": "unmeasured until the queue step grades it"})
    tally["accepted"] = len(accepted)

    for stale in out.glob("*.json"):
        stale.unlink()
    for task_file, task, sidecar in accepted:
        shutil.copyfile(task_file, out / task_file.name)
        shutil.copyfile(task_file.with_name(task_file.name[:-5] + ".lift.json"),
                        meta / "sidecars" / (task_file.name[:-5] + ".lift.json"))
    dump = lambda name, items: (meta / name).write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in items), encoding="utf-8")
    dump("heads.jsonl", heads)
    dump("refused.jsonl", refused)
    dump("twin-decisions.jsonl", decisions)
    dump("trust.jsonl", trust)
    census = {"schema": 1, "language": lang, "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "vericoded_files": tally["files"], "counts": dict(tally),
              "lifter_checks_run": bool(args.with_check), "lifter_wall_seconds": round(lift_seconds, 1),
              "lifter_verdicts": summary.get("verdict_counts") or summary.get("verdicts"),
              "lifter_refusals": dict(lifter_refusals.most_common()),
              "render_refusals": dict(Counter(r["reason"] for r in refused if r["stage"] == "render").most_common()),
              "select_refusals": dict(Counter(r["reason"].split(" (")[0].split(":")[0]
                                              for r in refused if r["stage"] == "select").most_common()),
              "native_verdicts": dict(Counter(v.get("verdict") for v in native.values())),
              "accepted": len(accepted), "heads": len(heads),
              "dedupe_against": [str(d) for d in args.dedupe_against or []],
              "license": LICENSE, "split": str(args.split), "pool": args.pool, "pool_size": len(pool)}
    (meta / "lift-census.json").write_text(json.dumps(census, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (meta / "vericoding-rows.json").write_text(
        json.dumps({k: {"source": v.get("source"), "source-id": v.get("source-id")} for k, v in rows.items()
                    if k.startswith(LANGS[lang]["prefix"])}), encoding="utf-8")
    return census


_HEADS_CACHE: dict = {}


def trows_for_heads(trows: dict, rows: dict) -> dict:
    """The task rows lift_corpora.head_for reads, with Clever's `clever_N` source ids read
    as the HumanEval index they are, so the HumanEval gate sees every alias."""
    key = id(trows)
    if key not in _HEADS_CACHE:
        fixed = {}
        for k, r in trows.items():
            r2 = dict(r)
            if (r.get("source") == "clever" or str(r.get("source-id", "")).startswith("clever")):
                m = re.search(r"(\d+)", str(r.get("source-id", "")))
                if m:
                    r2["source-id"] = f"humaneval_{int(m.group(1)):03d} (clever_{m.group(1)})"
            fixed[k] = r2
        _HEADS_CACHE[key] = fixed
    return _HEADS_CACHE[key]


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--language", required=True, choices=sorted(LANGS))
    ap.add_argument("--vericoding", required=True, help="a checkout of vericoding-benchmark")
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--pool", default="v5")
    ap.add_argument("--jobs", type=int, default=2, help="lifter jobs (each runs dafny)")
    ap.add_argument("--native-jobs", type=int, default=2, help="equivalence checks at once (each runs a prover)")
    ap.add_argument("--with-check", action="store_true", help="run the lifter's own Dafny check stage")
    ap.add_argument("--dedupe-against", action="append", help="a lifted-tasks directory whose problems are skipped")
    ap.add_argument("--resume", action="store_true")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    census = build(parse_args(argv))
    print(json.dumps({k: census[k] for k in ("language", "vericoded_files", "counts", "native_verdicts", "accepted",
                                              "heads")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
