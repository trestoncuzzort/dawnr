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
each problem whose every point it passes is then asked on 100 inputs drawn like its
first point (t/twin_draws.py): it claims the program as its twin unless the two answer
some drawn input differently, and a program any gated problem claims is refused. The
points alone refused coincidences (1 to 3 points per problem; on 2026-09-26, 179
refusals, and single problems "twinned" 9 to 13 unrelated programs). This is the
2026-09-25 behavioural rule (t/behavioural_decontam.py, Riddell et al. arXiv:2403.04811)
applied program-against-reference, as differential testing against the ground truth
(EvalPlus, https://ar5iv.labs.arxiv.org/html/2305.01210), because these corpora's own ids
cannot be trusted to name the pool's problems (vericoding numbers APPS its own way: 0 of
13 in-pool ids matched by text, 2026-09-26). The pool must be all here: a split whose
recorded pool size differs from the pool loaded is refused (the worktree failure mode).

Outputs: --out holds one task JSON per accepted task and nothing else (the
t/out/lifted-tasks layout the corpus builder globs); everything else goes to the
sibling directory <out>.meta/: sidecars/<task>.lift.json, heads.jsonl, refused.jsonl
(every refusal with its reason), twin-decisions.jsonl (every program with a candidate
twin problem: each candidate's draw verdict and the decision), lift-census.json (counts
per corpus and refusal reason), and the lifter's own run directory and the staged inputs.
Kernel grading is not done here: the seven-kernel verdict comes from the queue step named
in t/LIFT-2026-09-26.md.

    python3 t/lift_corpora.py --recover-twins --out t/out/lifted-tasks-2026-09-26 \
        --split t/out/loop/split-v5.json --vericoding DIR --humaneval-dafny DIR [--recovered DIR]

re-decides an existing lift's twin refusals under the drawn-input rule and never writes
the lift: it reads <out>.meta (refused.jsonl, the lifter's records in lift/, staged/, the
census), replays every gate on each program the lift refused as a twin, and writes only
the programs no gated problem claims now to <out>-recovered/, with its own .meta:
staged/ and sidecars/ for them, heads.jsonl in the lift's row format, twin-decisions.jsonl
(every twin refusal read: its candidate problems, the draw verdict for each, the decision)
and lift-census.json. The queue grades it: bash t/r12_data_queue.sh lift-2026-09-26-recovered.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import behavioural_decontam as bd                                # noqa: E402
import loop_filter                                               # noqa: E402
import loop_locallm                                              # noqa: E402
import relabel                                                   # noqa: E402
import spec_experiment as se                                     # noqa: E402
import surface                                                   # noqa: E402
import twin_draws                                                # noqa: E402
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
TWIN_REASON = re.compile(r"^passes every test point of gated problem (\d+) \((.+)\)$")   # a twin refusal's reason
RECOVERY_KIND = "twin recovery"   # the census --recover-twins writes says so; no other directory is ever replaced


# --------------------------------------------------------------- staging --

def read_vericoding_rows(src: Path) -> dict[str, dict]:
    """id -> task row of vericoding's jsonl/dafny_tasks.jsonl (its description, source and source-id)."""
    rows = {}
    jsonl = src / "jsonl" / "dafny_tasks.jsonl"
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["id"]] = row
    return rows


def vericoding_stem(f: Path) -> str:
    return "vericoding_" + f.name.split("_", 1)[0]


def stage_vericoding(src: Path, staged: Path) -> dict[str, dict]:
    """Copy vericoded/D*_vericoded.dfy to staged/vericoding_<ID>.dfy; return id -> task row
    (the jsonl's description, source and source-id)."""
    rows = read_vericoding_rows(src)
    staged.mkdir(parents=True, exist_ok=True)
    for f in sorted((src / "vericoded").glob("D*_vericoded.dfy")):
        shutil.copyfile(f, staged / f"{vericoding_stem(f)}.dfy")
    return rows


def humaneval_stem(f: Path) -> str:
    return "humaneval_dafny_" + re.sub(r"[^A-Za-z0-9_]", "_", f.stem)


def read_humaneval_texts(src: Path) -> dict[str, str]:
    """stem -> description (the sentence after "function `name`:" in text-descriptions/NNN-name.txt)."""
    descriptions = {}
    for f in sorted(src.glob("*.dfy")):
        text_file = src / "text-descriptions" / f"{f.stem}.txt"
        if text_file.exists():
            text = humaneval_description(text_file.read_text(encoding="utf-8"))
            if text:
                descriptions[humaneval_stem(f)] = text
    return descriptions


def stage_humaneval_dafny(src: Path, staged: Path) -> dict[str, str]:
    """Copy NNN-name.dfy to staged/humaneval_dafny_NNN_name.dfy; return stem -> description
    (the sentence after "function `name`:" in text-descriptions/NNN-name.txt)."""
    staged.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob("*.dfy")):
        shutil.copyfile(f, staged / f"{humaneval_stem(f)}.dfy")
    return read_humaneval_texts(src)


def source_files(vericoding: Path, humaneval: Path) -> dict[str, Path]:
    """Every staged stem the two checkouts give, with the file staging copies (the stage_* naming)."""
    files = {vericoding_stem(f): f for f in sorted((vericoding / "vericoded").glob("D*_vericoded.dfy"))}
    files.update({humaneval_stem(f): f for f in sorted(humaneval.glob("*.dfy"))})
    return files


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


def load_gating(split_path: str, pool_name: str) -> tuple[relabel.Gates, dict, dict[tuple, list[int]]]:
    """The gates, the pool and the gated problems by signature. Refused loudly when the pool loaded is
    not the one the split describes (behavioural_decontam.load_split: its version and its size): in a
    git worktree the untracked data under t/out and nl/data is missing, spec_experiment.pool silently
    shrinks, and a twin gate built on the smaller pool admits what the whole pool would refuse."""
    split = json.loads(Path(split_path).read_text(encoding="utf-8"))
    pool = se.pool(pool_name)
    bd.load_split(pool, pool_name, Path(split_path))
    gates = relabel.load_gates(split, split_path)
    return gates, pool, gated_index(pool, gates)


def twin_of(task: dict, index: dict[tuple, list[int]], pool: dict, gates: relabel.Gates,
            runner=None, evidence: list | None = None) -> tuple[int, str] | None:
    """The first gated problem that claims this program as its behavioural twin, with why it is gated.

    A candidate is a gated problem of the program's signature whose every test point the program
    passes. Until 2026-09-26 that alone refused the program, and with 1 to 3 points per problem it
    refused coincidences. Each candidate is now asked on drawn inputs (twin_draws.draw_check, the
    EvalPlus differential test against the reference, https://ar5iv.labs.arxiv.org/html/2305.01210):
    it claims the program unless the two answer some drawn input differently, and a reference that
    will not run, or no draw, keeps the claim. Every candidate is asked, in index order, so
    `evidence` (a list, when given) receives one record per candidate with the gate that made it
    one. `runner` (twin_draws.runner) caches each reference's answers across programs."""
    runner = runner or twin_draws.runner(pool)
    first = None
    for tid in index.get(relabel.task_signature(task), []):
        points = pool[tid]["points"]
        if not points or not all(se.run_point(task, point)["verdict"] == "pass" for point in points):
            continue
        check = twin_draws.draw_check(task, tid, pool[tid], runner)
        check["gate"] = gates.forbids(tid) or "gated"
        if evidence is not None:
            evidence.append(check)
        if check["twin"] and first is None:
            first = (tid, check["gate"])
    return first


def screen(stem: str, task: dict, vericoding_rows: dict, humaneval_texts: dict, pool: dict, gates: relabel.Gates,
           gate: loop_filter.TrainingDataGate, index: dict, runner) -> dict:
    """Every gate, in order, for one lifted task: the one code path of a lift and of --recover-twins.

    {"refused": the census's refusal label, None when admitted; "reason": the refused.jsonl reason, or
    head_for's; "head": the head row or None; "twin_check": one draw record per candidate twin problem,
    [] when the twin gate was not reached or found none; "twin_of": the problem that claims it}."""
    verdict = {"refused": None, "reason": "", "head": None, "twin_check": [], "twin_of": None}
    head, reason, named = head_for(stem, task, vericoding_rows, humaneval_texts, pool, gates)
    if head is None and reason.startswith("names HumanEval"):
        return {**verdict, "refused": reason.split(", ")[1], "reason": reason}
    try:
        document = surface.print_task(task).strip() + "\n"
    except surface.SurfaceError as error:
        # The lifter keeps Dafny's identifiers; a few are t keywords (a local named
        # `len`, 2026-09-26) and have no notation in t's surface syntax, so the task
        # cannot become a document. Refused by name; renaming is the lifter's job.
        return {**verdict, "refused": "no t notation", "reason": f"no t surface notation: {error}"}
    if not gate.admit(document, [task["name"]], named):
        return {**verdict, "refused": "gates", "reason": "held-out, listed or dev id under an alias"}
    evidence: list = []
    twin = twin_of(task, index, pool, gates, runner, evidence)
    if twin is not None:
        return {**verdict, "refused": "twin", "twin_check": evidence, "twin_of": twin[0],
                "reason": f"passes every test point of gated problem {twin[0]} ({twin[1]})"}
    return {**verdict, "head": head, "reason": reason, "twin_check": evidence}


def decision_row(task: dict, source: str, verdict: dict, admitted: str, refused_as: str | None = None) -> dict:
    """One twin-decisions.jsonl row: the program, every candidate problem with its draw verdict, the decision."""
    row = {"name": task["name"], "source": source, "candidates": verdict["twin_check"],
           "decision": "refused" if verdict["refused"] else admitted, "twin_of": verdict["twin_of"],
           "reason": (verdict["reason"] if verdict["refused"]
                      else "every candidate problem answered some drawn input differently")}
    if refused_as is not None:
        row["refused_as"] = refused_as
    return row


def hung_path_for(out: Path) -> Path:
    """Beside the directory being written: a reference that swallowed its timeout is named here before the
    process exits (twin_draws.runner), and the next run refuses it by name."""
    return out.with_name(out.name + ".twin-hung.jsonl")


# ------------------------------------------------------------------- main --

def build(args) -> dict:
    out = Path(args.out)
    meta = out.with_name(out.name + ".meta")
    staged = meta / "staged"
    lifted = meta / "lift"
    # before anything is staged or lifted: a pool that is not all here refuses the whole run
    gates, pool, index = load_gating(args.split, args.pool)
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

    gate = loop_filter.TrainingDataGate(frozenset(gates.held_out | gates.dev))
    runner = twin_draws.runner(pool, hung_path_for(out))

    accepted, heads, refused, decisions = [], [], [], []
    per_source: dict[str, Counter] = {SOURCE_VERICODING: Counter(), SOURCE_HUMANEVAL_DAFNY: Counter()}
    for task_file, task, sidecar in lifted_tasks(lifted):
        stem = task_file.name.split(".", 1)[0]
        source = source_of(stem)
        tally = per_source[source]
        tally["lifted"] += 1
        verdict = screen(stem, task, vericoding_rows, humaneval_texts, pool, gates, gate, index, runner)
        if verdict["twin_check"]:
            decisions.append(decision_row(task, source, verdict, "admitted"))
        if verdict["refused"]:
            tally["refused: " + verdict["refused"]] += 1
            refused.append({"name": task["name"], "source": source, "reason": verdict["reason"]})
            continue
        accepted.append((task_file, task, sidecar))
        head = verdict["head"]
        if head is None:
            tally["no head: " + verdict["reason"].split(":")[0]] += 1
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
    (meta / "twin-decisions.jsonl").write_text("".join(json.dumps(d, sort_keys=True) + "\n" for d in decisions),
                                               encoding="utf-8")
    census = {"schema": 1, "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "staged_files": staged_count, "lifter_checks_run": bool(args.with_check),
              "lifter_wall_seconds": round(lift_seconds, 1),
              "lifter_verdicts": summary.get("verdict_counts") or summary.get("verdicts"),
              "lifter_refusals": dict(refusals(lifted).most_common()),
              "per_source": {s: dict(c) for s, c in per_source.items()},
              "accepted": len(accepted), "heads": len(heads), "refused": len(refused),
              "gated_problems_by_signature": sum(len(v) for v in index.values()),
              "twin_draws": {"per_problem": twin_draws.DRAWS, "seed": twin_draws.SEED, "rule": twin_draws.RULE,
                             "sources": list(twin_draws.SOURCES),
                             "programs_with_candidates": len(decisions),
                             "cleared": sum(1 for d in decisions if d["decision"] == "admitted"),
                             "references_refused": {str(k): v for k, v in runner.refuse.items()}},
              "licenses": LICENSES, "split": str(args.split), "pool": args.pool, "pool_size": len(pool)}
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
    if census.get("kind") == RECOVERY_KIND:
        # its census and twin-decisions.jsonl are its report; this one would overwrite the lift's
        raise SystemExit(f"REFUSED: {out} is a --recover-twins output, not a lift; read {meta / 'twin-decisions.jsonl'}")
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
    if census.get("twin_draws"):
        twin_text = ["Every lifted program ran against the test points of every held-out, dev-split and listed",
                     "problem of its signature; each problem whose every point it passed then ran its reference",
                     f"against the program on {census['twin_draws']['per_problem']} inputs drawn like its first point "
                     "(`t/twin_draws.py`), and",
                     "claims the program as its twin unless the two answer some drawn input differently (a reference",
                     "that will not run keeps the claim). Each such program's candidates and verdicts are in",
                     "`twin-decisions.jsonl` beside the census."]
    else:   # a lift gated before 2026-09-26's draws: the points alone decided
        twin_text = ["Every lifted program ran against the test points of every held-out, dev-split and listed",
                     "problem of its signature (the 2026-09-25 behavioural rule applied program-against-reference,",
                     "because vericoding's APPS numbering is not the pool's: 0 of 13 in-pool ids matched by text)."]
    lines += [""] + twin_text + [
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


def claim_destination(recovered: Path, rmeta: Path) -> None:
    """Refuse a destination --recover-twins did not write, before any work: an existing .meta must hold a
    census of RECOVERY_KIND, and a task directory without its .meta (a run that died between its two
    moves, or somebody else's directory) is named, never replaced."""
    if rmeta.exists():
        try:
            kind = json.loads((rmeta / "lift-census.json").read_text(encoding="utf-8")).get("kind")
        except (OSError, ValueError, AttributeError):
            kind = None
        if kind != RECOVERY_KIND:
            raise SystemExit(f"REFUSED: {rmeta} exists and was not written by --recover-twins; move it aside")
    elif recovered.exists():
        raise SystemExit(f"REFUSED: {recovered} exists without {rmeta.name}, so no finished --recover-twins run "
                         "wrote it; move it aside")


def publish(recovered: Path, rmeta: Path, keep: list, meta: Path, heads: list, decisions: list, census: dict) -> None:
    """The recovered tasks and their .meta written under temporary names beside their final paths, then
    moved into place, the tasks first and the .meta (which holds the census) last, so the census exists
    only beside a complete set: Luigi's atomic writes, https://luigi.readthedocs.io/en/stable/luigi_patterns.html
    (its completion check is an existence check, and so is the queue step's)."""
    tag = f".partial-{os.getpid()}"
    for stale in [*recovered.parent.glob(recovered.name + ".partial-*"), *rmeta.parent.glob(rmeta.name + ".partial-*")]:
        shutil.rmtree(stale)                  # a temporary a dead run never moved
    tmp_d, tmp_m = recovered.with_name(recovered.name + tag), rmeta.with_name(rmeta.name + tag)
    tmp_d.mkdir(parents=True)
    (tmp_m / "sidecars").mkdir(parents=True)
    (tmp_m / "staged").mkdir()
    for task_file, stem in keep:
        shutil.copyfile(task_file, tmp_d / task_file.name)
        sidecar = task_file.name[:-len(".json")] + ".lift.json"
        shutil.copyfile(task_file.with_name(sidecar), tmp_m / "sidecars" / sidecar)
        shutil.copyfile(meta / "staged" / f"{stem}.dfy", tmp_m / "staged" / f"{stem}.dfy")
    (tmp_m / "heads.jsonl").write_text("".join(json.dumps(h, sort_keys=True) + "\n" for h in heads), encoding="utf-8")
    (tmp_m / "twin-decisions.jsonl").write_text("".join(json.dumps(d, sort_keys=True) + "\n" for d in decisions),
                                                encoding="utf-8")
    (tmp_m / "lift-census.json").write_text(json.dumps(census, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if rmeta.exists():
        shutil.rmtree(rmeta)                  # the old census goes first: it must never stand beside new tasks
    if recovered.exists():
        shutil.rmtree(recovered)
    os.replace(tmp_d, recovered)
    os.replace(tmp_m, rmeta)


def _verdicts(check_list: list) -> str:
    return ", ".join(str(c["problem"]) + " " + c["verdict"] for c in check_list)


def recover_twins(args) -> dict:
    """--recover-twins: re-decide an existing lift's twin refusals under twin_of's drawn-input rule.

    Reads <out>.meta (refused.jsonl, the lifter's records in lift/, staged/, lift-census.json) and never
    writes the lift: a grading job may be reading it, and it moves task files out of <out> as their checks
    fail, so the programs are read from the lifter's own records. Every program the lift refused as a
    twin goes through every gate again (screen, the lift's own code path); the ones no gated problem
    claims now are written with their heads, sidecars and staged sources to a new directory (default
    <out>-recovered) and its .meta, beside twin-decisions.jsonl (every twin refusal read, recovered or
    not) and lift-census.json. Refused loudly: a pool the split does not describe, another pool or split
    than the lift's, a count of twin refusals the lift's census does not state, a refusal without exactly
    one lifter record, a staged source the given checkout does not hold byte for byte, a problem the lift
    named that the program no longer passes, and a destination this mode did not write."""
    out = Path(args.out)
    meta = out.with_name(out.name + ".meta")
    recovered = Path(args.recovered) if args.recovered else out.with_name(out.name + "-recovered")
    rmeta = recovered.with_name(recovered.name + ".meta")
    if not (args.vericoding and args.humaneval_dafny):
        raise SystemExit("REFUSED: --recover-twins writes heads from the sources' own English: give --vericoding and "
                         "--humaneval-dafny, the checkouts the lift staged from")
    for need in (meta / "refused.jsonl", meta / "lift-census.json", meta / "lift", meta / "staged"):
        if not need.exists():
            raise SystemExit(f"REFUSED: {need} is missing; --recover-twins re-decides an existing lift's .meta")
    read_only = [out.resolve(), meta.resolve()]
    for target in (recovered.resolve(), rmeta.resolve()):
        if any(target == q or target.is_relative_to(q) or q.is_relative_to(target) for q in read_only):
            raise SystemExit(f"REFUSED: {target} is the lift being re-decided, or holds it, or lies inside it; "
                             "the lift is only read")
    claim_destination(recovered, rmeta)
    census = json.loads((meta / "lift-census.json").read_text(encoding="utf-8"))
    if census.get("pool") != args.pool:
        raise SystemExit(f"REFUSED: the lift was gated under pool {census.get('pool')!r}, this run asks for {args.pool!r}")
    if Path(str(census.get("split"))).resolve() != Path(args.split).resolve():
        raise SystemExit(f"REFUSED: the lift was gated under split {census.get('split')!r}, this run gives {args.split!r}")
    rows = [json.loads(line) for line in (meta / "refused.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    twin_rows = [row for row in rows if TWIN_REASON.match(row["reason"])]
    stated = sum(int(c.get("refused: twin", 0)) for c in (census.get("per_source") or {}).values())
    if len(twin_rows) != stated:
        raise SystemExit(f"REFUSED: {meta / 'refused.jsonl'} holds {len(twin_rows)} twin refusals, the lift's census "
                         f"states {stated}")
    records: dict[str, list[Path]] = {}
    for task_file, task, _sidecar in lifted_tasks(meta / "lift"):
        records.setdefault(task["name"], []).append(task_file)
    unmatched = [row["name"] for row in twin_rows if len(records.get(row["name"], [])) != 1]
    if unmatched:
        raise SystemExit(f"REFUSED: {len(unmatched)} twin refusal(s) without exactly one lifter record in "
                         f"{meta / 'lift'}: {unmatched[:5]}")
    sources = source_files(Path(args.vericoding), Path(args.humaneval_dafny))
    for row in twin_rows:
        stem = records[row["name"]][0].name.split(".", 1)[0]
        staged, source = meta / "staged" / f"{stem}.dfy", sources.get(stem)
        if not staged.exists() or source is None or source.read_bytes() != staged.read_bytes():
            raise SystemExit(f"REFUSED: {stem}: the staged source and the given checkout's copy differ or one is "
                             "missing; heads must come from the checkout the lift staged")

    gates, pool, index = load_gating(args.split, args.pool)
    vericoding_rows = read_vericoding_rows(Path(args.vericoding))
    humaneval_texts = read_humaneval_texts(Path(args.humaneval_dafny))
    gate = loop_filter.TrainingDataGate(frozenset(gates.held_out | gates.dev))
    runner = twin_draws.runner(pool, hung_path_for(recovered))
    started = time.monotonic()
    decisions, keep, heads = [], [], []
    per_source: dict[str, Counter] = {SOURCE_VERICODING: Counter(), SOURCE_HUMANEVAL_DAFNY: Counter()}
    for i, row in enumerate(twin_rows, 1):
        task_file = records[row["name"]][0]
        task = json.loads(task_file.read_text(encoding="utf-8"))
        stem = task_file.name.split(".", 1)[0]
        source = source_of(stem)
        tally = per_source[source]
        tally["twin refusals read"] += 1
        named = int(TWIN_REASON.match(row["reason"]).group(1))
        verdict = screen(stem, task, vericoding_rows, humaneval_texts, pool, gates, gate, index, runner)
        if verdict["refused"] in (None, "twin") and named not in [c["problem"] for c in verdict["twin_check"]]:
            raise SystemExit(f"REFUSED: {row['name']} does not pass every test point of gated problem {named}, which "
                             "the lift named; the pool or the gates are not the lift's")
        decisions.append(decision_row(task, source, verdict, "recovered", row["reason"]))
        if verdict["refused"]:
            tally["refused: " + verdict["refused"]] += 1
        else:
            keep.append((task_file, stem))
            tally["accepted"] += 1
            if verdict["head"] is None:
                tally["no head: " + verdict["reason"].split(":")[0]] += 1
            else:
                tally["head: " + verdict["head"]["curation"]] += 1
                heads.append(verdict["head"])
        print(f"  {i}/{len(twin_rows)} {row['name']}: {decisions[-1]['decision']} "
              f"({_verdicts(verdict['twin_check']) or verdict['reason']})", file=sys.stderr, flush=True)

    new_census = {"schema": 1, "kind": RECOVERY_KIND, "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "from": str(args.out), "from_census_when": census.get("when"),
                  "rule": twin_draws.RULE, "draws_per_problem": twin_draws.DRAWS, "seed": twin_draws.SEED,
                  "sources": list(twin_draws.SOURCES),
                  "twin_refusals_read": len(twin_rows), "accepted": len(keep), "heads": len(heads),
                  "refused": len(twin_rows) - len(keep),
                  "candidate_verdicts": dict(Counter(c["verdict"] for d in decisions for c in d["candidates"])),
                  "still_claimed_by": dict(Counter(str(d["twin_of"]) for d in decisions
                                                   if d["twin_of"] is not None).most_common()),
                  "per_source": {s: dict(c) for s, c in per_source.items()},
                  "references_refused": {str(k): v for k, v in runner.refuse.items()},
                  "lifter_checks_run": census.get("lifter_checks_run"), "licenses": LICENSES,
                  "split": str(args.split), "pool": args.pool, "pool_size": len(pool),
                  "gated_problems_by_signature": sum(len(v) for v in index.values()),
                  "wall_seconds": round(time.monotonic() - started, 1)}
    publish(recovered, rmeta, keep, meta, heads, decisions, new_census)
    return new_census


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
    ap.add_argument("--recover-twins", action="store_true",
                    help="re-decide the twin refusals of the lift in --out on drawn inputs; the lift is only read")
    ap.add_argument("--recovered", help="where --recover-twins writes (default: <out>-recovered, and its .meta)")
    args = ap.parse_args(argv)
    if args.report_only:
        print(write_report(Path(args.out)))
        return 0
    if args.recover_twins:
        census = recover_twins(args)
        print(json.dumps({k: census[k] for k in ("twin_refusals_read", "accepted", "refused", "heads",
                                                  "candidate_verdicts", "pool", "pool_size", "wall_seconds")}, indent=1))
        return 0
    census = build(args)
    print(write_report(Path(args.out)))
    print(json.dumps({k: census[k] for k in ("staged_files", "lifter_verdicts", "accepted", "heads", "refused",
                                              "lifter_checks_run")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
