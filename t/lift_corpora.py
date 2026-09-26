#!/usr/bin/env python3
"""t/lift_corpora.py -- lift released corpora of verified Dafny programs into t, with
their own English as heads, through the same gates every training document passes
(2026-09-26).

    python3 t/lift_corpora.py --vericoding DIR --humaneval-dafny DIR --out t/out/lifted-tasks-2026-09-26 \
        --split t/out/loop/split-v5.json [--pool v5] [--jobs 4] [--with-check]

Why: locallm's fine-tune memorizes its ~300-document corpus (train 0.11 against
held-out 0.68 nats per token at step 300, 2026-09-26). Regularizers cannot fix a
50K-token corpus; more verified, English-headed documents can. Two released corpora
carry both a verified Dafny program and English written for it:

  vericoding-benchmark  github.com/Beneficial-AI-Foundation/vericoding-benchmark (MIT):
                        vericoded/D*_vericoded.dfy, one AI-written verified solution per
                        spec, and jsonl/dafny_tasks.jsonl with a `vc-description` per id
                        (research receipts 4f74eccb9928 and cd343f6a8f1c).
  HumanEval-Dafny       github.com/JetBrains-Research/HumanEval-Dafny (Apache-2.0):
                        132 human-written .dfy solutions and text-descriptions/<n>.txt
                        (receipt cd343f6a8f1c).

Each .dfy goes through t/lifter.py (LIFTER-DESIGN.md: resolve, parse, classify, rewrite,
check), which refuses what t's fragment cannot express by name. A lifted task keeps the
source's English verbatim as its `Problem:` head; nothing is written for a task whose
source has none. Curation is per source and stated in every head row: a HumanEval task
whose index names a pool problem with test points is kept only when the lifted program
passes them (`test`); every other head is the source's own statement for that task
(`source-statement`), human-written for HumanEval-Dafny and for the problem statements
vericoding inherited (APPS, HumanEval, numpy docs), never verified against the program
here.

Gates, in order, each a refusal by name: the held-out ids under every alias and the
same-task exclusions (loop_filter.TrainingDataGate over the merged policy), the dev
split (loop_filter.r12_dev_ids), a HumanEval index that names a gated problem, and a
behavioural twin: the lifted program is run through the t interpreter on the test
points of every gated problem (held-out, dev, listed) whose signature it matches, and
one it passes on every point is refused as that problem's twin. This is the 2026-09-25
behavioural rule (t/behavioural_decontam.py, Riddell et al. arXiv:2403.04811) applied
program-against-reference, because these corpora's own ids cannot be trusted to name
the pool's problems (vericoding numbers APPS its own way: 0 of 13 in-pool ids matched
by text, 2026-09-26).

Outputs: --out holds one task JSON per accepted task and nothing else (the
t/out/lifted-tasks layout the corpus builder globs); everything else goes to the
sibling directory <out>.meta/: sidecars/<task>.lift.json, heads.jsonl, refused.jsonl
(every refusal with its reason), lift-census.json (counts per corpus and refusal
reason), and the lifter's own run directory and the staged inputs. Kernel grading is not done here: the seven-kernel verdict
comes from the queue step named in t/LIFT-2026-09-26.md.
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
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import loop_filter                                               # noqa: E402
import loop_locallm                                              # noqa: E402
import relabel                                                   # noqa: E402
import spec_experiment as se                                     # noqa: E402
import surface                                                   # noqa: E402
from heads_from_sources import example_lines                     # noqa: E402

SOURCE_VERICODING = "vericoding"
SOURCE_HUMANEVAL_DAFNY = "humaneval-dafny"
CURATION_TEST = "test"                    # passes the pool problem's own points through the t interpreter
CURATION_STATEMENT = "source-statement"   # the source's own English for this task, not verified against the program
LICENSES = {SOURCE_VERICODING: "MIT (Beneficial AI Foundation, 2025)",
            SOURCE_HUMANEVAL_DAFNY: "Apache-2.0 (JetBrains Research)"}
VERICODING_SOURCE_NOTE = {"apps": "APPS problem statement (vericoding's own numbering, not the pool's)",
                          "humaneval": "HumanEval problem, index humaneval_NNN",
                          "dafnybench": "DafnyBench program, described by the benchmark",
                          "verified_cogen": "verified-cogen task", "verina": "Verina task",
                          "numpy_triple": "numpy documentation", "numpy_simple": "numpy documentation",
                          "bignum": "bignum task"}


# --------------------------------------------------------------- staging --

def stage_vericoding(src: Path, staged: Path) -> dict[str, dict]:
    """Copy vericoded/D*_vericoded.dfy to staged/vericoding_<ID>.dfy; return id -> task row
    (the jsonl's description, source and source-id)."""
    rows = {}
    jsonl = src / "jsonl" / "dafny_tasks.jsonl"
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["id"]] = row
    staged.mkdir(parents=True, exist_ok=True)
    for f in sorted((src / "vericoded").glob("D*_vericoded.dfy")):
        vid = f.name.split("_", 1)[0]
        shutil.copyfile(f, staged / f"vericoding_{vid}.dfy")
    return rows


def stage_humaneval_dafny(src: Path, staged: Path) -> dict[str, str]:
    """Copy NNN-name.dfy to staged/humaneval_dafny_NNN_name.dfy; return stem -> description
    (the sentence after "function `name`:" in text-descriptions/NNN-name.txt)."""
    descriptions = {}
    staged.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob("*.dfy")):
        stem = "humaneval_dafny_" + re.sub(r"[^A-Za-z0-9_]", "_", f.stem)
        shutil.copyfile(f, staged / f"{stem}.dfy")
        text_file = src / "text-descriptions" / f"{f.stem}.txt"
        if text_file.exists():
            text = humaneval_description(text_file.read_text(encoding="utf-8"))
            if text:
                descriptions[stem] = text
    return descriptions


def humaneval_description(text: str) -> str | None:
    """The English after "function `name`:" in a HumanEval-Dafny description file, as one line."""
    match = re.search(r"function `[^`]+`:\s*(.*)", text, re.S)
    if not match:
        return None
    return " ".join(match.group(1).split()) or None


# ----------------------------------------------------------------- lifting --

def run_lifter(staged: Path, out: Path, jobs: int, with_check: bool) -> dict:
    """t/lifter.py --dir over the staged files; returns its run_summary.json."""
    cmd = [sys.executable, str(HERE / "lifter.py"), "--dir", str(staged), "--out", str(out),
           "--jobs", str(jobs)]
    if not with_check:
        cmd.append("--skip-check")
    subprocess.run(cmd, check=False)
    summary = out / "run_summary.json"
    if not summary.exists():
        raise SystemExit(f"the lifter wrote no {summary}")
    return json.loads(summary.read_text(encoding="utf-8"))


def lifted_tasks(out: Path) -> list[tuple[Path, dict, dict]]:
    """Every (task file, task, sidecar) the lifter wrote under out."""
    result = []
    for sidecar in sorted(out.glob("*.lift.json")):
        task_file = sidecar.with_name(sidecar.name[:-len(".lift.json")] + ".json")
        if not task_file.exists():
            continue
        result.append((task_file, json.loads(task_file.read_text(encoding="utf-8")),
                       json.loads(sidecar.read_text(encoding="utf-8"))))
    return result


def refusals(out: Path) -> Counter:
    """The lifter's refusal reasons over every outcome record, by reason."""
    tally: Counter = Counter()
    for outcome in out.glob("*.outcome.json"):
        record = json.loads(outcome.read_text(encoding="utf-8"))
        for key in ("resolve_refusal", "parse_refusal"):
            if record.get(key):
                tally[f"{key.split('_')[0]}:{record[key].get('reason')}"] += 1
        for method in record.get("methods", []):
            if method.get("refusal"):
                tally[f"classify:{method['refusal'].get('reason')}"] += 1
    return tally


# ------------------------------------------------------------------ heads --

def source_of(stem: str) -> str:
    if stem.startswith("vericoding_"):
        return SOURCE_VERICODING
    if stem.startswith("humaneval_dafny_"):
        return SOURCE_HUMANEVAL_DAFNY
    raise ValueError(f"not a staged stem: {stem}")


def humaneval_index(source_id: str | None, stem: str) -> int | None:
    """The HumanEval problem number a vericoding humaneval row or a HumanEval-Dafny stem names."""
    if source_id and source_id.startswith("humaneval"):
        m = re.search(r"(\d+)", source_id)
        return int(m.group(1)) if m else None
    m = re.match(r"humaneval_dafny_(\d+)_", stem)
    return int(m.group(1)) if m else None


def head_for(stem: str, task: dict, vericoding_rows: dict, humaneval_texts: dict, pool: dict,
             gates: relabel.Gates) -> tuple[dict | None, str, list[int]]:
    """(head row or None, reason, the pool ids this task's source names)."""
    source = source_of(stem)
    named: list[int] = []
    if source == SOURCE_VERICODING:
        vid = stem[len("vericoding_"):]
        row = vericoding_rows.get(vid)
        if row is None:
            return None, "no task row in dafny_tasks.jsonl", named
        problem = " ".join((row.get("vc-description") or "").split())
        if not problem:
            return None, "no vc-description", named
        index = humaneval_index(row.get("source-id"), stem)
        note = f"{VERICODING_SOURCE_NOTE.get(row.get('source'), row.get('source'))}, {row.get('source-id')}"
    else:
        problem = humaneval_texts.get(stem)
        if not problem:
            return None, "no text-descriptions file", named
        index = humaneval_index(None, stem)
        note = f"HumanEval-Dafny {stem}"
    examples: list[str] = []
    curation = CURATION_STATEMENT
    if index is not None:
        tid = se.HUMANEVAL_BASE + index
        named.append(tid)
        why = gates.forbids(tid)
        if why:
            return None, f"names HumanEval {index}, a {why} id", named
        entry = pool.get(tid)
        if entry is not None and entry.get("points"):
            verdicts = [se.run_point(task, point)["verdict"] for point in entry["points"]]
            if any(v != "pass" for v in verdicts):
                return None, f"HumanEval {index} tests: " + ", ".join(sorted(set(verdicts))), named
            examples = example_lines(task, entry["points"])
            curation = CURATION_TEST
    return {"name": task["name"], "problem": problem, "examples": examples, "source": source,
            "curation": curation, "origin": note}, curation, named


# ------------------------------------------------------------------ gates --

def gated_index(pool: dict, gates: relabel.Gates) -> dict[tuple, list[int]]:
    """Every gated pool problem (held-out, listed, dev) with test points, by signature."""
    index: dict[tuple, list[int]] = {}
    for tid in sorted(pool):
        if not gates.forbids(tid) or not pool[tid].get("points"):
            continue
        sig = relabel.problem_signature(pool[tid])
        if sig is not None:
            index.setdefault(sig, []).append(tid)
    return index


def twin_of(task: dict, index: dict[tuple, list[int]], pool: dict, gates: relabel.Gates) -> tuple[int, str] | None:
    """The first gated problem whose every test point the program passes, with why it is gated."""
    for tid in index.get(relabel.task_signature(task), []):
        points = pool[tid]["points"]
        if points and all(se.run_point(task, point)["verdict"] == "pass" for point in points):
            return tid, gates.forbids(tid) or "gated"
    return None


# ------------------------------------------------------------------- main --

def build(args) -> dict:
    out = Path(args.out)
    meta = out.with_name(out.name + ".meta")
    staged = meta / "staged"
    lifted = meta / "lift"
    out.mkdir(parents=True, exist_ok=True)
    (meta / "sidecars").mkdir(parents=True, exist_ok=True)
    if staged.exists() and not args.resume:
        shutil.rmtree(staged)
    vericoding_rows = stage_vericoding(Path(args.vericoding), staged) if args.vericoding else {}
    humaneval_texts = stage_humaneval_dafny(Path(args.humaneval_dafny), staged) if args.humaneval_dafny else {}
    staged_count = len(list(staged.glob("*.dfy")))
    if staged_count == 0:
        raise SystemExit("nothing staged: give --vericoding and/or --humaneval-dafny")
    started = time.monotonic()
    summary = run_lifter(staged, lifted, args.jobs, args.with_check)
    lift_seconds = time.monotonic() - started

    split = json.loads(Path(args.split).read_text(encoding="utf-8"))
    gates = relabel.load_gates(split, args.split)
    pool = se.pool(args.pool)
    index = gated_index(pool, gates)
    gate = loop_filter.TrainingDataGate(frozenset(gates.held_out | gates.dev))

    accepted, heads, refused = [], [], []
    per_source: dict[str, Counter] = {SOURCE_VERICODING: Counter(), SOURCE_HUMANEVAL_DAFNY: Counter()}
    for task_file, task, sidecar in lifted_tasks(lifted):
        stem = task_file.name.split(".", 1)[0]
        source = source_of(stem)
        tally = per_source[source]
        tally["lifted"] += 1
        head, reason, named = head_for(stem, task, vericoding_rows, humaneval_texts, pool, gates)
        if head is None and reason.startswith("names HumanEval"):
            tally["refused: " + reason.split(", ")[1]] += 1
            refused.append({"name": task["name"], "source": source, "reason": reason})
            continue
        document = surface.print_task(task).strip() + "\n"
        if not gate.admit(document, [task["name"]], named):
            tally["refused: gates"] += 1
            refused.append({"name": task["name"], "source": source, "reason": "held-out, listed or dev id under an alias"})
            continue
        twin = twin_of(task, index, pool, gates)
        if twin is not None:
            tally["refused: twin"] += 1
            refused.append({"name": task["name"], "source": source,
                            "reason": f"passes every test point of gated problem {twin[0]} ({twin[1]})"})
            continue
        accepted.append((task_file, task, sidecar))
        if head is None:
            tally["no head: " + reason.split(":")[0]] += 1
        else:
            tally["head: " + head["curation"]] += 1
            heads.append(head)
        tally["accepted"] += 1

    for stale in out.glob("*.json"):
        stale.unlink()
    for task_file, task, sidecar in accepted:
        shutil.copyfile(task_file, out / task_file.name)
        shutil.copyfile(task_file.with_name(task_file.name[:-5] + ".lift.json"),
                        meta / "sidecars" / (task_file.name[:-5] + ".lift.json"))
    (meta / "heads.jsonl").write_text("".join(json.dumps(h, sort_keys=True) + "\n" for h in heads), encoding="utf-8")
    (meta / "refused.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in refused), encoding="utf-8")
    census = {"schema": 1, "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "staged_files": staged_count, "lifter_checks_run": bool(args.with_check),
              "lifter_wall_seconds": round(lift_seconds, 1),
              "lifter_verdicts": summary.get("verdict_counts") or summary.get("verdicts"),
              "lifter_refusals": dict(refusals(lifted).most_common()),
              "per_source": {s: dict(c) for s, c in per_source.items()},
              "accepted": len(accepted), "heads": len(heads), "refused": len(refused),
              "gated_problems_by_signature": sum(len(v) for v in index.values()),
              "licenses": LICENSES, "split": str(args.split), "pool": args.pool}
    (meta / "lift-census.json").write_text(json.dumps(census, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # the vericoding rows' source per id, so the report can split the counts by where vericoding got each task
    (meta / "vericoding-rows.json").write_text(
        json.dumps({k: {"source": v.get("source"), "source-id": v.get("source-id")} for k, v in vericoding_rows.items()}),
        encoding="utf-8")
    return census


def write_report(out: Path) -> Path:
    """t/LIFT-<date>.md from the meta directory: counts per corpus and per vericoding source,
    the lifter's refusal reasons ranked, the gates' refusals, and the queue step that grades
    the result. Written from the files, so it can be regenerated."""
    meta = out.with_name(out.name + ".meta")
    census = json.loads((meta / "lift-census.json").read_text(encoding="utf-8"))
    heads = [json.loads(l) for l in (meta / "heads.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    refused = [json.loads(l) for l in (meta / "refused.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    accepted = sorted(p.name[:-5] for p in out.glob("*.json"))
    staged = sorted(p.stem for p in (meta / "staged").glob("*.dfy"))
    rows_file = meta / "vericoding-rows.json"
    vericoding_rows = json.loads(rows_file.read_text(encoding="utf-8")) if rows_file.exists() else {}

    def vsource(stem: str) -> str:
        row = vericoding_rows.get(stem[len("vericoding_"):]) if stem.startswith("vericoding_") else None
        return f"vericoding/{row['source']}" if row else source_of(stem)

    def stem_of(task_name: str) -> str:
        # task names are the staged stem lower-cased plus "__" and the method
        lowered = {s.lower(): s for s in staged}
        return lowered.get(task_name.split("__", 1)[0], task_name)

    staged_by = Counter(vsource(s) for s in staged)
    accepted_by = Counter(vsource(n.split(".", 1)[0]) for n in accepted)
    refused_by_source = Counter(vsource(stem_of(r["name"])) for r in refused)
    heads_by = Counter((vsource(stem_of(h["name"])), h["curation"]) for h in heads)
    refused_by = Counter(("twin of a " + r["reason"].split("(")[-1].rstrip(")") + " problem") if "gated problem" in r["reason"]
                         else r["reason"] for r in refused)
    lines = [f"# Lifting released verified corpora into t, {census['when'][:10]}", "",
             "locallm's fine-tune memorizes its ~300-document corpus (train 0.11 against held-out 0.68",
             "nats per token at step 300). Regularizers cannot fix a 50K-token corpus; more verified,",
             "English-headed documents can. This is what two released corpora of verified Dafny programs",
             "with their own English yield through t's lifter (`t/lift_corpora.py`, `t/lifter.py`).", "",
             "## Sources", "",
             "| corpus | licence | staged .dfy | lifted tasks | accepted after the gates | heads |",
             "|---|---|---:|---:|---:|---:|"]
    for src in sorted(staged_by):
        lic = LICENSES[SOURCE_VERICODING] if src.startswith("vericoding") else LICENSES[SOURCE_HUMANEVAL_DAFNY]
        lifted_here = accepted_by.get(src, 0) + refused_by_source.get(src, 0)
        head_n = sum(v for (s, _c), v in heads_by.items() if s == src)
        lines.append(f"| {src} | {lic} | {staged_by[src]} | {lifted_here} | {accepted_by.get(src, 0)} | {head_n} |")
    verdicts = census.get("lifter_verdicts") or {}
    lines += ["", f"Staged files: {census['staged_files']}. The lifter's verdicts: "
              + ", ".join(f"{k} {v}" for k, v in sorted(verdicts.items())) + ".",
              "Lifter checks run: " + ("yes." if census["lifter_checks_run"] else
                                       "NO: the machine that lifted has no dafny; the queue step reruns the lifter "
                                       "with checks on the grading machine before anything is graded."),
              "", "## Why the lifter refused what it refused", "", "| reason | files or methods |", "|---|---:|"]
    for reason, n in sorted((census.get("lifter_refusals") or {}).items(), key=lambda kv: -kv[1])[:25]:
        lines.append(f"| {reason} | {n} |")
    lines += ["", "## Heads, by source and curation", "", "| source | curation | heads |", "|---|---|---:|"]
    for (src, cur), n in sorted(heads_by.items()):
        lines.append(f"| {src} | {cur} | {n} |")
    lines += ["", "`test`: the lifted program passes the pool problem's own points through the t interpreter",
              "(HumanEval indexes that name a pool problem). `source-statement`: the source's own English for",
              "the task, human-written (HumanEval-Dafny; the problem statements vericoding inherited), not",
              "verified against the program here. A task with no English keeps no head.", "",
              "## Refused by the gates", "", "| reason | tasks |", "|---|---:|"]
    for reason, n in refused_by.most_common():
        lines.append(f"| {reason} | {n} |")
    lines += ["", "Every lifted program ran against the test points of every held-out, dev-split and listed",
              "problem of its signature (the 2026-09-25 behavioural rule applied program-against-reference,",
              "because vericoding's APPS numbering is not the pool's: 0 of 13 in-pool ids matched by text).",
              "HumanEval indexes that name a gated problem are refused before any run.", "",
              "## What is not measured", "",
              "- The seven-kernel verdict (clean in all seven) for every accepted task: unmeasured until",
              "  `bash t/r12_data_queue.sh lift-2026-09-26` runs on the grading machine. It first reruns the",
              "  lifter's own check stage (equivalence lemmas and the differential run under dafny), drops",
              "  every task that fails it, then grades the rest as the 785 DafnyBench lifts were graded.",
              "- dafny-disco (metareflection, 81,342 synthetic Dafny programs, CC-BY-SA-4.0): not lifted; the",
              "  share-alike licence cannot be carried by this repository, the programs are class- and",
              "  datatype-heavy (outside t's fragment), and the parquet needs pyarrow, which no machine here has.",
              "- ATLAS (arXiv:2512.10173): no released data.",
              "- Clover and DafnyBench: already lifted (t/COVERAGE-lifted-785.md, t/HEADS-2026-09-25.md).", "",
              "## The queue step", "",
              "    bash t/r12_data_queue.sh lift-2026-09-26", "",
              "Written, not run. After it: copy `t/out/COVERAGE-lifted-2026-09-26.md` to",
              "`t/COVERAGE-lifted-2026-09-26.md` and give the corpus builder `--lifted-dir t/out/lifted-tasks-2026-09-26`",
              "`--lifted-table t/COVERAGE-lifted-2026-09-26.md --heads t/out/lifted-tasks-2026-09-26.meta/heads.jsonl`",
              "(a builder option that does not exist yet; see the track report's callers_to_update).", ""]
    path = HERE / f"LIFT-{census['when'][:10]}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vericoding", help="a checkout of vericoding-benchmark")
    ap.add_argument("--humaneval-dafny", help="a checkout of HumanEval-Dafny")
    ap.add_argument("--out", required=True, help="the lifted-tasks directory to write (t/out layout)")
    ap.add_argument("--split", required=True, help="the split whose eval ids are held out")
    ap.add_argument("--pool", default="v5")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--with-check", action="store_true",
                    help="run the lifter's check stage (needs dafny); off, the tasks carry no checker verdict")
    ap.add_argument("--resume", action="store_true", help="keep an existing staged directory")
    ap.add_argument("--report-only", action="store_true", help="write t/LIFT-<date>.md from an existing --out")
    args = ap.parse_args(argv)
    if args.report_only:
        print(write_report(Path(args.out)))
        return 0
    census = build(args)
    print(write_report(Path(args.out)))
    print(json.dumps({k: census[k] for k in ("staged_files", "lifter_verdicts", "accepted", "heads", "refused",
                                              "lifter_checks_run")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
