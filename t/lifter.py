"""The lifter's top-level entry point: one .dfy file in, one row per
gradable method out, plus a CLI wrapper around `lift_census.build_table`
for the full corpus run.

Reads LIFTER-DESIGN.md sections 2 (architecture -- the "data flow per
file" paragraph this module implements verbatim: resolve -> parse ->
classify (refuse or continue) -> rewrite -> check_wf -> interp.Reference
-> twin_for -> checker verify -> differential run -> row), 8 (provenance
sidecar -- the `<task>.lift.json` file this module writes beside every
emitted task), 12 (test plan -- step 7, "only then the corpus run, whose
output is the table"), 13 (expected numbers this module's corpus run is
checked against), 18.2 (rewrite vocabulary, for the sidecar's field
names), and LIFTER-DECISIONS.md decisions 9 (one task per gradable method)
and 17 (a lifted-but-instrument-refused task gets its own column).

`lifter.py` is glue, not a new decision point: it is not named in section
2's architecture table because it makes none of that table's decisions
itself -- every `Refusal` reason, every rewrite, every check verdict
comes from the module named for it (`lift_resolve.py`,
`lift_parse.py`, `lift_classify.py`, `lift_rewrite.py`, `lift_check.py`).
This module's only jobs are: call them in the right order, stop at the
first refusal, write the outputs the pipeline produced to disk, and
expose a CLI.

Stub-aware by requirement (not a design choice this module gets to make
on its own -- the implementation plan handed to this file's author says
so explicitly): while any of the five modules above is still a stub
(its function body is a bare `raise NotImplementedError`), calling it
must not crash a whole corpus run. Every call into one of those five
modules is therefore wrapped by `_stage_call` below, which turns a
`NotImplementedError` into a `Refusal(reason="module-not-implemented",
...)` for that file/method and lets the run continue with the next
file; any OTHER exception is caught the same way with
`reason="error"` (the exception text is kept as `token`) rather than
ever propagating out of `lift_file` -- "a run never crashes on one
file, it records the exception in that file's record."
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from lift_ast import LiftRecord, Refusal

import corpora
import lift_check
import lift_classify
import lift_parse
import lift_resolve
import lift_rewrite

DEFAULT_CORPUS_DIR = corpora.CORPUS_DIR
DEFAULT_CENSUS_JSON = corpora.CENSUS_JSON
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "out" / "lift"
HARD_JOBS_CAP = 4  # each job may run dafny; this box allows at most 4 concurrent


@dataclass
class MethodOutcome:
    """One gradable method's fate, per LIFTER-DESIGN.md section 2's "row
    is per gradable METHOD, not per file" rule (decision 9).

    `method` is the method's source name. `refusal` is the `Refusal` from
    whichever stage stopped the pipeline (`classify`, `rewrite`, or
    `check`), or `None` if the method lifted and every check passed --
    note a twin refusal (`no-witness`, etc.) does NOT set this field
    (section 5: "in the fragment, cannot count" is not "out of the
    fragment"); it is recorded on `record.twin_rung`/`record
    .twin_witness` being `None` plus the twin reason living in `record`,
    per `lift_check.CheckOutput`'s own docs. `task` is the emitted t task
    JSON dict, `None` if refused before rewrite completed. `record` is
    the full `LiftRecord` sidecar, `None` only when refused before
    `lift_rewrite.rewrite` ran (a `classify`-stage refusal has no record
    to build yet).

    Two fields beyond the interfaces contract, both additive and both
    defaulted so no existing caller breaks (documented as signature
    changes): `checked` is `True` only when `lift_check.check` actually
    ran and returned with `refusal is None` -- section 8's own
    "lifter lifted and checked" phrase needs exactly this bit, and
    `refusal is None` alone cannot supply it (`--skip-check` also leaves
    `refusal` `None` without ever having checked anything).
    `interp_points`/`interp_first_value` mirror
    `lift_check.CheckOutput`'s same-named fields, needed by
    `lift_census.CensusRow` (which this module has no other way to
    reach, since `CheckOutput` itself is not returned to this dataclass's
    caller, only folded into `record`/`refusal`)."""
    method: str
    refusal: Optional[Refusal] = None
    task: Optional[dict] = None
    record: Optional[LiftRecord] = None
    checked: bool = False
    interp_points: int = 0
    interp_first_value: object = None


@dataclass
class FileOutcome:
    """One file's fate: `resolve_refusal` is set (and `methods` empty)
    when `lift_resolve.resolve` itself failed (`resolve-failure` or a
    resolve-stage `parse-failure`, before any method-level work is
    possible); `parse_refusal` is set (and `methods` empty) when
    `lift_parse.parse` raised `LiftParseError` on rprint text that DID
    resolve; otherwise `methods` has one `MethodOutcome` per gradable
    method found by `lift_parse.gradable_methods` (possibly empty, if the
    file has no gradable method at all -- `no-method` or `no-ensures`,
    recorded as a synthetic file-level entry in `methods` with that
    `Refusal` and `method=""`, rather than a third refusal field, since
    "no gradable method" is itself a section-5 reason with a line)."""
    source_path: Path
    resolve_refusal: Optional[Refusal] = None
    parse_refusal: Optional[Refusal] = None
    methods: list[MethodOutcome] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage-call wrapper: see the module docstring's "Stub-aware by
# requirement" paragraph.
# ---------------------------------------------------------------------------

def _stage_call(stage: str, token: str, line: int, fn, *args, **kwargs):
    """Call `fn(*args, **kwargs)`. Returns `(result, None)` on success, or
    `(None, Refusal)` if `fn` raised -- `NotImplementedError` becomes
    `reason="module-not-implemented"`, anything else becomes
    `reason="error"` with the exception's type and message (and, for a
    non-NotImplementedError, a one-line traceback tail printed to stderr
    so a real bug is not silently swallowed -- it is still recorded, not
    raised, but it is not invisible either)."""
    try:
        return fn(*args, **kwargs), None
    except NotImplementedError:
        return None, Refusal(reason="module-not-implemented", token=token, line=line, stage=stage)
    except Exception as e:  # noqa: BLE001 - a corpus run must never crash on one file
        print(f"lifter: unexpected {type(e).__name__} in {token}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr, limit=4)
        return None, Refusal(reason="error", token=f"{type(e).__name__}: {e}", line=line, stage=stage)


def _scratch_dfy_path(out_dir: Optional[Path], stem: str, method_name: str) -> Path:
    if out_dir is not None:
        # Created here, not by _write_outcome: the check stage writes its
        # .check.dfy into this directory BEFORE any outcome is written, so a
        # fresh --out made every early file raise FileNotFoundError inside
        # lift_check and get filed as `refused:error`. A lift that a missing
        # directory turned into a refusal is a corrupted row, not a slow one.
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / f"{stem}.{method_name}.check.dfy"
    fd, name = tempfile.mkstemp(suffix=".dfy", prefix=f"{stem}.{method_name}.")
    os.close(fd)
    return Path(name)


# ---------------------------------------------------------------------------
# Serialisation: LiftRecord/Refusal <-> plain dict, for the per-method
# sidecar (`<name>.<method>.lift.json`) and the per-file resumability
# marker (`<name>.outcome.json`). This module owns both file formats.
# ---------------------------------------------------------------------------

def _refusal_to_dict(r: Optional[Refusal]) -> Optional[dict]:
    if r is None:
        return None
    return {"reason": r.reason, "token": r.token, "line": r.line, "stage": r.stage}


def _refusal_from_dict(d: Optional[dict]) -> Optional[Refusal]:
    if d is None:
        return None
    return Refusal(reason=d["reason"], token=d["token"], line=d["line"], stage=d["stage"])


def _record_to_dict(rec: Optional[LiftRecord]) -> Optional[dict]:
    if rec is None:
        return None
    return {
        "source_path": rec.source_path,
        "method": rec.method,
        "rprint_sha256": rec.rprint_sha256,
        "rename_map": {k: {"t_name": v.t_name, "reason": v.reason}
                       for k, v in rec.rename_map.items()},
        "rewrites": [{"rule": w.rule, "line": w.line} for w in rec.rewrites],
        "clauses_added": [{"rule": c.rule, "text": c.text} for c in rec.clauses_added],
        "clauses_dropped": [{"rule": c.rule, "count": c.count} for c in rec.clauses_dropped],
        "decreases_origin": dict(rec.decreases_origin),
        "twin_rung": rec.twin_rung,
        "twin_witness": rec.twin_witness,
        "checker_verdicts": dict(rec.checker_verdicts),
        "differential_verdict": rec.differential_verdict,
        "dafny_exit_codes": dict(rec.dafny_exit_codes),
        "warnings": list(rec.warnings),
    }


def _record_from_dict(d: Optional[dict]) -> Optional[LiftRecord]:
    if d is None:
        return None
    from lift_ast import ClauseAdded, ClauseDropped, Rename, Rewrite
    return LiftRecord(
        source_path=d["source_path"],
        method=d["method"],
        rprint_sha256=d["rprint_sha256"],
        rename_map={k: Rename(t_name=v["t_name"], reason=v["reason"])
                    for k, v in d.get("rename_map", {}).items()},
        rewrites=[Rewrite(rule=w["rule"], line=w["line"]) for w in d.get("rewrites", [])],
        clauses_added=[ClauseAdded(rule=c["rule"], text=c["text"])
                       for c in d.get("clauses_added", [])],
        clauses_dropped=[ClauseDropped(rule=c["rule"], count=c["count"])
                         for c in d.get("clauses_dropped", [])],
        decreases_origin=dict(d.get("decreases_origin", {})),
        twin_rung=d.get("twin_rung"),
        twin_witness=d.get("twin_witness"),
        checker_verdicts=dict(d.get("checker_verdicts", {})),
        differential_verdict=d.get("differential_verdict"),
        dafny_exit_codes=dict(d.get("dafny_exit_codes", {})),
        warnings=list(d.get("warnings", [])),
    )


def _marker_path(out_dir: Path, stem: str) -> Path:
    return out_dir / f"{stem}.outcome.json"


def _write_outcome(outcome: FileOutcome, out_dir: Path, stem: str) -> None:
    """Write every method's task/sidecar file (for methods that reached
    `lift_rewrite.rewrite`) plus the per-file `<stem>.outcome.json`
    resumability marker, all under `out_dir`. Windows-safe: UTF-8,
    explicit `newline="\\n"`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    method_entries = []
    for mo in outcome.methods:
        safe_method = mo.method if mo.method else "_"
        task_file = None
        record_file = None
        if mo.task is not None:
            task_file = f"{stem}.{safe_method}.json"
            with (out_dir / task_file).open("w", encoding="utf-8", newline="\n") as f:
                json.dump(mo.task, f, indent=2, sort_keys=True)
                f.write("\n")
        if mo.record is not None:
            record_file = f"{stem}.{safe_method}.lift.json"
            with (out_dir / record_file).open("w", encoding="utf-8", newline="\n") as f:
                json.dump(_record_to_dict(mo.record), f, indent=2, sort_keys=True)
                f.write("\n")
        method_entries.append({
            "method": mo.method,
            "refusal": _refusal_to_dict(mo.refusal),
            "checked": mo.checked,
            "interp_points": mo.interp_points,
            "interp_first_value": mo.interp_first_value,
            "task_file": task_file,
            "record_file": record_file,
        })
    marker = {
        "source_path": str(outcome.source_path),
        "resolve_refusal": _refusal_to_dict(outcome.resolve_refusal),
        "parse_refusal": _refusal_to_dict(outcome.parse_refusal),
        "methods": method_entries,
    }
    with _marker_path(out_dir, stem).open("w", encoding="utf-8", newline="\n") as f:
        json.dump(marker, f, indent=2, sort_keys=True)
        f.write("\n")


def _load_outcome(out_dir: Path, stem: str, source_path: Path) -> Optional[FileOutcome]:
    """Reconstruct a `FileOutcome` from a previously written
    `<stem>.outcome.json` marker (and the task/sidecar files it points
    at), or `None` if no marker exists yet. This is the read half of
    resumability: `lift_file` calls this before doing any real work."""
    marker_path = _marker_path(out_dir, stem)
    if not marker_path.is_file():
        return None
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    outcome = FileOutcome(
        source_path=source_path,
        resolve_refusal=_refusal_from_dict(marker.get("resolve_refusal")),
        parse_refusal=_refusal_from_dict(marker.get("parse_refusal")),
    )
    for entry in marker.get("methods", []):
        task = None
        record = None
        if entry.get("task_file"):
            tp = out_dir / entry["task_file"]
            if tp.is_file():
                task = json.loads(tp.read_text(encoding="utf-8"))
        if entry.get("record_file"):
            rp = out_dir / entry["record_file"]
            if rp.is_file():
                record = _record_from_dict(json.loads(rp.read_text(encoding="utf-8")))
        outcome.methods.append(MethodOutcome(
            method=entry["method"],
            refusal=_refusal_from_dict(entry.get("refusal")),
            task=task,
            record=record,
            checked=bool(entry.get("checked", False)),
            interp_points=int(entry.get("interp_points", 0) or 0),
            interp_first_value=entry.get("interp_first_value"),
        ))
    return outcome


# ---------------------------------------------------------------------------
# lift_file
# ---------------------------------------------------------------------------

def lift_file(dfy_path: Path, out_dir: Optional[Path] = None,
              timeout_s: float = 120.0, force: bool = False,
              skip_check: bool = False) -> FileOutcome:
    """Run the full section-2 data-flow pipeline on one .dfy file.

    Input: `dfy_path` (a .dfy path -- section 2's per-file entry point);
    `out_dir` (optional: when given, every lifted method's task JSON is
    written to `<out_dir>/<name>.<method>.json` and its sidecar to
    `<out_dir>/<name>.<method>.lift.json` (`<name>` = `dfy_path.stem`,
    per this file's own "Build" instructions, which give the exact
    pattern -- the interfaces docstring's shorter `<method>.json` would
    collide across files sharing a method name), plus a per-file
    `<name>.outcome.json` resumability marker; when `None`, nothing is
    written and the caller uses `FileOutcome`/`MethodOutcome` directly --
    this is what `test_lifter.py`'s SEEDS-driven tests use, since they
    check the in-memory task against a hand-written fixture rather than a
    file on disk); `timeout_s` (the wall-clock timeout passed through to
    every dafny invocation `lift_resolve.resolve` and `lift_check.check`
    make).

    Two parameters beyond the interfaces contract (documented as
    signature changes, both additive with backward-compatible defaults):
    `force` (skip the resumability check below and always redo the
    work -- the "unless --force" half of "a source file whose record
    exists is skipped unless --force"); `skip_check` (stop after
    `lift_rewrite.rewrite`, never call `lift_check.check` -- the
    "resolve, parse, classify, rewrite only" mode).

    Resumability: when `out_dir` is given, not `force`d, and
    `<out_dir>/<name>.outcome.json` already exists, this function loads
    and returns that marker's `FileOutcome` without calling any of the
    five pipeline modules again -- true "does no work" reuse, not merely
    a fast recomputation.

    Output: one `FileOutcome`, containing one `MethodOutcome` per gradable
    method (decision 9: the table reports both the program count -- "in
    fragment iff every task lifts" -- and the method count; this function
    reports at method granularity only, the program-count view is
    `lift_census.py`'s to compute by folding over several files' worth of
    `FileOutcome`s).

    Steps, stopping this file/method's pipeline at the first refusal:
    `lift_resolve.resolve(dfy_path, timeout_s)` -> on `.refusal`, return a
    `FileOutcome` with `resolve_refusal` set and empty `methods`;
    otherwise `lift_parse.parse(.rprint_text)` -> on `LiftParseError`,
    return with `parse_refusal` set; otherwise
    `lift_parse.gradable_methods(module)`, and for each: `lift_classify
    .classify(module, method)` -> on `Refusal`, append a `MethodOutcome`
    with it and move to the next method; on `Liftable`, `lift_rewrite
    .rewrite(module, plan, str(dfy_path), rprint_sha256)`, then
    `lift_check.check(task, method, plan.closure, record, scratch_path,
    timeout_s)`, and append the resulting `MethodOutcome` (refusal set iff
    `CheckOutput.refusal` is not `None`).

    While any of those five modules is still a stub, a `NotImplementedError`
    from it is caught (see `_stage_call`) and recorded as
    `reason="module-not-implemented"` on that file's/method's outcome
    rather than propagating -- "a run never crashes on one file, it
    records the exception in that file's record" -- and processing of
    THIS file stops at that point (later stages cannot run without the
    earlier one's real output), but the caller's loop over many files
    continues.

    MAY decide: nothing beyond delegating to the modules above -- this
    function is glue (see the module docstring); it invents no refusal
    reason, no rewrite, and no verdict of its own.

    MAY NOT decide: any refusal reason, rewrite, or check verdict itself;
    all of those must trace back to a call into `lift_resolve.py`,
    `lift_parse.py`, `lift_classify.py`, `lift_rewrite.py`, or
    `lift_check.py`."""
    dfy_path = Path(dfy_path)
    stem = dfy_path.stem

    if out_dir is not None and not force:
        cached = _load_outcome(Path(out_dir), stem, dfy_path)
        if cached is not None:
            return cached

    outcome = FileOutcome(source_path=dfy_path)

    result, err = _stage_call("resolve", "lift_resolve.resolve", 0,
                               lift_resolve.resolve, dfy_path, timeout_s)
    if err is not None:
        outcome.resolve_refusal = err
        if out_dir is not None:
            _write_outcome(outcome, Path(out_dir), stem)
        return outcome
    if result.refusal is not None:
        outcome.resolve_refusal = result.refusal
        if out_dir is not None:
            _write_outcome(outcome, Path(out_dir), stem)
        return outcome

    try:
        module = lift_parse.parse(result.rprint_text)
    except lift_parse.LiftParseError as e:
        outcome.parse_refusal = Refusal(reason=getattr(e, "reason", None) or "parse-failure", token=e.token,
                                         line=e.line, stage="parse")
        if out_dir is not None:
            _write_outcome(outcome, Path(out_dir), stem)
        return outcome
    except NotImplementedError:
        outcome.parse_refusal = Refusal(reason="module-not-implemented",
                                         token="lift_parse.parse", line=0, stage="parse")
        if out_dir is not None:
            _write_outcome(outcome, Path(out_dir), stem)
        return outcome
    except Exception as e:  # noqa: BLE001
        print(f"lifter: unexpected {type(e).__name__} in lift_parse.parse: {e}",
              file=sys.stderr)
        traceback.print_exc(file=sys.stderr, limit=4)
        outcome.parse_refusal = Refusal(reason="error", token=f"{type(e).__name__}: {e}",
                                         line=0, stage="parse")
        if out_dir is not None:
            _write_outcome(outcome, Path(out_dir), stem)
        return outcome

    methods, err = _stage_call("parse", "lift_parse.gradable_methods", 0,
                                lift_parse.gradable_methods, module)
    if err is not None:
        outcome.parse_refusal = err
        if out_dir is not None:
            _write_outcome(outcome, Path(out_dir), stem)
        return outcome

    if not methods:
        outcome.methods.append(MethodOutcome(
            method="", refusal=Refusal(reason="no-method", token="", line=1, stage="parse")))
        if out_dir is not None:
            _write_outcome(outcome, Path(out_dir), stem)
        return outcome

    rprint_sha256 = hashlib.sha256(result.rprint_text.encode("utf-8")).hexdigest()

    for method in methods:
        method_name = getattr(method, "name", None) or ""
        method_line = getattr(method, "line", 0)

        plan_or_refusal, err = _stage_call(
            "classify", "lift_classify.classify", method_line,
            lift_classify.classify, module, method)
        if err is not None:
            outcome.methods.append(MethodOutcome(method=method_name, refusal=err))
            continue
        if isinstance(plan_or_refusal, Refusal):
            outcome.methods.append(MethodOutcome(method=method_name, refusal=plan_or_refusal))
            continue
        plan = plan_or_refusal

        rewrite_result, err = _stage_call(
            "rewrite", "lift_rewrite.rewrite", method_line,
            lift_rewrite.rewrite, module, plan, str(dfy_path), rprint_sha256)
        if err is not None:
            outcome.methods.append(MethodOutcome(method=method_name, refusal=err))
            continue
        task, record = rewrite_result.task, rewrite_result.record

        if skip_check:
            outcome.methods.append(MethodOutcome(
                method=method_name, task=task, record=record, checked=False))
            continue

        scratch = _scratch_dfy_path(Path(out_dir) if out_dir is not None else None,
                                     stem, method_name or "_")
        check_output, err = _stage_call(
            "check", "lift_check.check", method_line,
            lift_check.check, task, method, plan.closure, record, scratch, timeout_s)
        if err is not None:
            outcome.methods.append(MethodOutcome(
                method=method_name, task=task, record=record, refusal=err))
            continue
        outcome.methods.append(MethodOutcome(
            method=method_name,
            refusal=check_output.refusal,
            task=task,
            record=check_output.record,
            checked=(check_output.refusal is None),
            interp_points=check_output.interp_points,
            interp_first_value=check_output.interp_first_value,
        ))

    if out_dir is not None:
        _write_outcome(outcome, Path(out_dir), stem)
    return outcome


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _normalize_argv(argv: list[str]) -> list[str]:
    """Accept `--flag:value` (RUN-ON-WINDOWS.md's subprocess-flag
    convention) alongside argparse-native `--flag value` / `--flag=value`:
    rewrite the first `:` in a long option to `=` before argparse sees it."""
    out = []
    for a in argv:
        if a.startswith("--") and ":" in a and "=" not in a.split(":", 1)[0]:
            key, _, rest = a.partition(":")
            out.append(f"{key}={rest}")
        else:
            out.append(a)
    return out


def _print_file_outcome(dfy_path: Path, outcome: FileOutcome) -> None:
    if outcome.resolve_refusal is not None:
        r = outcome.resolve_refusal
        print(f"{dfy_path}: refused:{r.reason} at {r.line}")
        return
    if outcome.parse_refusal is not None:
        r = outcome.parse_refusal
        print(f"{dfy_path}: refused:{r.reason} at {r.line}")
        return
    for mo in outcome.methods:
        name = mo.method or "(file)"
        if mo.refusal is None:
            print(f"{dfy_path}: {name}: lifted")
        else:
            print(f"{dfy_path}: {name}: refused:{mo.refusal.reason} at {mo.refusal.line}")


def _outcome_verdicts(outcome: FileOutcome) -> list[tuple[Optional[str], str]]:
    """[(method_or_None, verdict_string)] for summary counting, where
    verdict_string is `"lifted"` or `"refused:<reason>"`."""
    if outcome.resolve_refusal is not None:
        return [(None, f"refused:{outcome.resolve_refusal.reason}")]
    if outcome.parse_refusal is not None:
        return [(None, f"refused:{outcome.parse_refusal.reason}")]
    out = []
    for mo in outcome.methods:
        v = "lifted" if mo.refusal is None else f"refused:{mo.refusal.reason}"
        out.append((mo.method or None, v))
    return out


def _collect_targets(args) -> list[Path]:
    if args.list is not None:
        names = [line.strip() for line in Path(args.list).read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.strip().startswith("#")]
        return [Path(args.corpus_dir) / name for name in names]
    if args.dir is not None:
        return sorted(Path(args.dir).glob("*.dfy"))
    return []


def _run_many(paths: list[Path], out_dir: Path, jobs: int, timeout_s: float,
              force: bool, skip_check: bool) -> dict:
    """Drive `lift_file` over `paths`, resumability-aware at the driver
    level too (a marker hit is never even dispatched to a worker, so a
    fully-resumed run truly does no work -- no subprocess pool, no
    per-file call at all): returns the run summary dict `main` writes to
    `<out_dir>/run_summary.json`."""
    jobs = max(1, min(jobs, HARD_JOBS_CAP))
    start = time.monotonic()

    todo: list[Path] = []
    resumed = 0
    verdict_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    per_file: list[dict] = []

    for p in paths:
        stem = p.stem
        if not force and _marker_path(out_dir, stem).is_file():
            cached = _load_outcome(out_dir, stem, p)
            if cached is not None:
                resumed += 1
                for _, verdict in _outcome_verdicts(cached):
                    verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
                    if verdict.startswith("refused:"):
                        reason = verdict[len("refused:"):]
                        reason_counts[reason] = reason_counts.get(reason, 0) + 1
                per_file.append({"file": str(p), "resumed": True,
                                  "verdicts": _outcome_verdicts(cached)})
                continue
        todo.append(p)

    def _finish(p: Path, outcome: FileOutcome) -> None:
        for _, verdict in _outcome_verdicts(outcome):
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
            if verdict.startswith("refused:"):
                reason = verdict[len("refused:"):]
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        per_file.append({"file": str(p), "resumed": False,
                          "verdicts": _outcome_verdicts(outcome)})

    if todo:
        if jobs == 1:
            for p in todo:
                outcome = lift_file(p, out_dir=out_dir, timeout_s=timeout_s,
                                     force=force, skip_check=skip_check)
                _finish(p, outcome)
        else:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                futures = {
                    pool.submit(_worker, str(p), str(out_dir), timeout_s, force,
                                skip_check): p
                    for p in todo
                }
                for fut in as_completed(futures):
                    p = futures[fut]
                    outcome = fut.result()
                    _finish(p, outcome)

    wall_s = time.monotonic() - start
    return {
        "files_total": len(paths),
        "files_resumed": resumed,
        "files_processed": len(todo),
        "wall_s": wall_s,
        "verdict_counts": verdict_counts,
        "refusal_reason_counts": reason_counts,
        "per_file": per_file,
    }


def _worker(dfy_path_str: str, out_dir_str: str, timeout_s: float,
            force: bool, skip_check: bool) -> FileOutcome:
    """Top-level (picklable) worker for the `--jobs > 1` pool: re-imports
    nothing special (this whole module is already import-safe under
    spawn), just calls `lift_file` in the child process."""
    return lift_file(Path(dfy_path_str), out_dir=Path(out_dir_str),
                      timeout_s=timeout_s, force=force, skip_check=skip_check)


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point. Windows-safe argument handling (per
    RUN-ON-WINDOWS.md: no shell-specific path assumptions, `pathlib`
    throughout; flags accept `--flag value`, `--flag=value`, and
    `--flag:value` alike, see `_normalize_argv`).

    Modes (mutually exclusive, checked in this order): a single `.dfy`
    path positional argument runs `lift_file` on it and prints its
    `FileOutcome` (one line per method: lifted, or `refused:<reason>` at
    `<line>`); `--list PATH` reads one corpus file name per line
    (resolved against `--corpus-dir`) and runs the multi-file driver;
    `--dir PATH` globs `*.dfy` under `PATH` and runs the same driver;
    `--census` runs `lift_census.build_table` over the full corpus
    (section 12 test plan step 7: "only then the corpus run, whose
    output is the table"), reading `census.json` and the DafnyBench
    ground_truth directory from `--census-json`/`--corpus-dir` (both
    required with `--census`), and an optional `--out` to write every
    lifted task and sidecar (resumable the same way as `--list`/`--dir`,
    since both go through `lift_file`).

    The multi-file driver (`--list`/`--dir`) additionally takes `--jobs N`
    (default 4, hard-capped at 4 -- each job may run dafny, and this is a
    shared box), `--out DIR` (default `t/out/lift`), `--force` (redo work
    even where a `<name>.outcome.json` record already exists), and
    `--skip-check` (stop after rewrite; never call `lift_check.check`). It
    writes `<out>/run_summary.json` (counts by verdict and by refusal
    reason, wall time, resumed-vs-processed split) in addition to every
    file's own `<name>.outcome.json` and `<name>.<method>.json`/
    `.lift.json` (written by `lift_file` itself).

    Prints the resulting table's summary counts (agree / lifter / census
    / undecided / gap-name, per section 8) to stdout in `--census` mode;
    prints per-file/per-method verdicts otherwise. Returns 0 on a
    completed run, non-zero on an argument error or an unhandled
    exception from the pipeline.

    Returns the process exit code (0 success, non-zero on error), per
    Python convention for a `main()` meant to be passed to `sys.exit`."""
    argv = sys.argv[1:] if argv is None else argv
    argv = _normalize_argv(argv)

    parser = argparse.ArgumentParser(
        description="Lift Dafny methods to t (LIFTER-DESIGN.md section 2).")
    parser.add_argument("file", nargs="?", default=None, type=Path,
                         help="single .dfy file to lift")
    parser.add_argument("--list", type=Path, default=None,
                         help="a file listing corpus file names, one per line")
    parser.add_argument("--dir", type=Path, default=None,
                         help="a directory of .dfy files to lift")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR,
                         help="base directory --list's names are resolved against, "
                              "and the DafnyBench directory for --census")
    parser.add_argument("--jobs", type=int, default=4,
                         help=f"parallel jobs for --list/--dir (hard cap {HARD_JOBS_CAP})")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR,
                         help="output directory for task/sidecar/marker files")
    parser.add_argument("--force", action="store_true",
                         help="redo work even where a record already exists")
    parser.add_argument("--skip-check", action="store_true",
                         help="resolve, parse, classify, rewrite only; never check")
    parser.add_argument("--timeout", type=float, default=120.0,
                         help="wall-clock timeout (seconds) per dafny invocation")
    parser.add_argument("--census", action="store_true",
                         help="run lift_census.build_table over the full corpus")
    parser.add_argument("--census-json", type=Path, default=DEFAULT_CENSUS_JSON,
                         help="census.json path, for --census")

    args = parser.parse_args(argv)

    if args.census:
        import lift_census
        rows = lift_census.build_table(args.census_json, args.corpus_dir,
                                        out_dir=args.out)
        summary = lift_census.summarize(rows)
        print(f"{len(rows)} rows ({summary.program_total} programs)")
        for verdict in ("agree", "lifter", "census", "undecided", "gap-name"):
            print(f"  {verdict}: {summary.disagreement_counts.get(verdict, 0)}")
        return 0

    if args.file is not None:
        outcome = lift_file(args.file, out_dir=args.out, timeout_s=args.timeout,
                             force=args.force, skip_check=args.skip_check)
        _print_file_outcome(args.file, outcome)
        return 0

    targets = _collect_targets(args)
    if not targets:
        parser.error("give a .dfy file, --list PATH, --dir PATH, or --census")

    args.out.mkdir(parents=True, exist_ok=True)
    summary = _run_many(targets, args.out, args.jobs, args.timeout,
                         args.force, args.skip_check)
    with (args.out / "run_summary.json").open("w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"{summary['files_total']} files: {summary['files_resumed']} resumed, "
          f"{summary['files_processed']} processed, {summary['wall_s']:.2f}s wall")
    print("verdict counts:")
    for verdict, count in sorted(summary["verdict_counts"].items()):
        print(f"  {verdict}: {count}")
    if summary["files_resumed"] and not summary["files_processed"]:
        print("all files already had records; nothing re-run (resumable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
