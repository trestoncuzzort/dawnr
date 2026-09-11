#!/usr/bin/env python3
"""t/conformance.py: the ROADMAP 13.4 conformance suite, one command.

    python3 t/conformance.py [--jobs N] [--flake 3] [--out t/CONFORMANCE.md]

13.4's bar (ROADMAP.md) is a probe suite built from two sources this module
never restates, only reads and grades:

  1. fuzz_lower.py's hand-built probes, `fuzz_lower.probes()`. Each probe
     already carries its own documented expectation -- the second argument
     to that function's own `add(task, expect, why, adversarial=False)`
     call, stored on the task as `_expect` -- so `probe_manifest()` below
     reads `_expect`/`_why`/`_adversarial` off each probe rather than
     re-deciding what it should be. Measuring every `_expect` value
     fuzz_lower.probes() actually sets (2026-09-11, 53 probes) gives
     exactly OUTCOME_VOCAB below: "verified", "refuted", "vacuous"
     (Outcome.VACUOUS -- accepted, but the spec was too weak to mean
     anything), "wf-refused" (the checker must refuse the task before any
     kernel sees it) and "lower-error" (every kernel's own lowering must
     reject the token).

  2. metamorphic.py's named survivors, `metamorphic.TRANSFORMS`: 20 rewrites
     (rename, add-zero, mul-one, sub-zero, double-neg, comm-add,
     reassoc-add, and-true, or-false, not-not, de-morgan, swap-if,
     swap-cmp, reorder, let-copy, pad, self-assign, spec-add-zero,
     spec-not-not, req-or-false), each carrying the SPEC.md clause that
     makes it meaning-preserving (metamorphic.py's own docstring,
     "SOUNDNESS OF THE REWRITES THEMSELVES"). Every one of these is a
     PROPERTY -- verdict(T(task)) == verdict(task) for whatever task T
     applies to, not a fixed input/output pair -- so nothing here invents
     an expected value for the transform itself. What IS a task: one
     instance of each applicable transform over one fixed, already-
     conforming base, t/tasks/abs.t, whose real column reads VERIFIED
     in every one of the seven committed AGREEMENT.md columns (measured
     2026-09-11, `grep '^| abs ' t/AGREEMENT.md`). A transform with no
     applicable site in abs's body/spec (metamorphic.py's own
     applicability rule inside `variants_of`) is named as not-applicable
     here rather than silently omitted -- see `metamorphic_manifest`'s
     second return value.

Both manifests are graded through the same cell machinery run_par.py uses:
`run_par.probe_backends()` for the seven-kernel probe (unchanged import,
not reimplemented), and `verifiers.cell_pair` at the same default flake
(n=3) for the kernel calls themselves. The one place this driver departs
from `run_par.lower_and_dispatch` is exception handling around
`harness.twin_cached`: two probes (fz_p_nodiv today) are deliberately fed a
token the reference interpreter itself refuses to evaluate, by design (the
probe's whole point is that a LOWERING must reject the token, not that the
interpreter can classify it), and `lower_and_dispatch` has no path for
that. This module's driver catches it and falls back to lowering the real
body alone per column, exactly the handling `fuzz_lower.run()` already
carries for the same reason (see that function's own comment on
`fz_p_nodiv`) -- copied here because this module needs it standalone, not
duplicated logic newly invented.

check_wf lives directly in fuzz_lower.py in this worktree (HEAD edc9c32 at
the time this module was written; the split into a stand-alone t/check_wf.py
described for "tonight" landed on commit 6e87c3d, which this branch's history
does not yet contain -- `git merge-base --is-ancestor 6e87c3d HEAD` measured
false here). `fz.check_wf` is the same function either way; nothing below
depends on which module defines it.

Exit code: 1 if any probe or metamorphic cell reads FAIL, 0 otherwise.
Writes t/CONFORMANCE.md (or --out) in AGREEMENT.md's row format, one
"expected" column and a PASS/FAIL/N-A suffix per kernel cell.
"""
from __future__ import annotations

import argparse
import importlib
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                                              # noqa: E402
import tasks_io
import fuzz_lower as fz                                      # noqa: E402
import metamorphic as mm                                     # noqa: E402
import run_par                                                # noqa: E402
from verifiers import (cell_pair, flake_check, mp_context, sha256_file,  # noqa: E402
                       acquire_run_lock)

BACKENDS = run_par.BACKENDS

# The complete vocabulary fuzz_lower.probes() actually assigns to `_expect`,
# measured directly (`{p["_expect"] for p in fuzz_lower.probes()}`,
# 2026-09-11, 53 probes): verified, refuted, vacuous (Outcome.VACUOUS --
# accepted, but the spec was too weak to mean anything), wf-refused and
# lower-error. "wf-refused" and "lower-error" are graded outside the seven-
# kernel cell (see run_items below); the other three are graded against the
# real column's Outcome string directly.
OUTCOME_VOCAB = {"verified", "refuted", "vacuous", "wf-refused", "lower-error"}

BASE_TASK_PATH = tasks_io.find(HERE / "tasks", "abs")
# abs: `| abs | verified / refuted |` x7 in the committed t/AGREEMENT.md,
# measured 2026-09-11 with `grep '^| abs ' t/AGREEMENT.md`.
BASE_EXPECT = "verified"
METAMORPHIC_SEED = 20260911          # fixed: a deterministic manifest


# ===========================================================================
# 1. The manifest.
# ===========================================================================

def probe_manifest() -> list[dict]:
    """One entry per fuzz_lower.probes() task, carrying that probe's own
    declared `_expect`/`_why`/`_adversarial` -- read, not restated."""
    out = []
    for p in fz.probes():
        exp = p["_expect"]
        assert exp in OUTCOME_VOCAB, (
            f"{p['name']}: fuzz_lower._expect {exp!r} outside OUTCOME_VOCAB "
            f"{OUTCOME_VOCAB} -- the manifest's vocabulary is stale")
        out.append({"name": p["name"], "task": p, "expected": exp,
                    "why": p.get("_why", ""),
                    "adversarial": bool(p.get("_adversarial", False)),
                    "kind": "probe"})
    return out


def metamorphic_manifest() -> tuple[list[dict], list[str], list]:
    """(items, not_applicable, tripwire_bugs). `items` is one conformance
    task per TRANSFORMS entry that applies to BASE_TASK_PATH's body/spec,
    named `mm_<transform>_<base name>`, expected BASE_EXPECT throughout.
    `not_applicable` names every TRANSFORMS entry that produced no variant
    (metamorphic.py's own applicability rule -- abs has no add/mul/
    de-morgan/reorder/let-copy/self-assign/req-or-false site). A non-empty
    `tripwire_bugs` means metamorphic.py's own soundness argument for some
    rewrite was contradicted by the interpreter tripwire on THIS base task;
    each becomes a hard FAIL row, never silently dropped."""
    base = tasks_io.load_task(BASE_TASK_PATH)
    rng = random.Random(METAMORPHIC_SEED)
    variants, bugs = mm.variants_of(base, rng)
    applied = {label for label, _ in variants}
    items = []
    for label, variant in variants:
        v = dict(variant)
        vname = f"mm_{label.replace('-', '_')}_{base['name']}"
        v["name"] = vname
        items.append({"name": vname, "task": v, "expected": BASE_EXPECT,
                      "why": f"metamorphic.py TRANSFORMS[{label!r}] on "
                            f"{base['name']}: verdict-preserving per that "
                            f"module's own soundness argument for the "
                            f"rewrite",
                      "adversarial": False, "kind": "metamorphic"})
    not_applicable = sorted(name for name, _ in mm.TRANSFORMS
                            if name not in applied)
    return items, not_applicable, bugs


def build_manifest() -> tuple[list[dict], list[str], list]:
    probes = probe_manifest()
    meta, not_applicable, bugs = metamorphic_manifest()
    names = [it["name"] for it in probes + meta]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"conformance manifest has duplicate task names: {dupes}"
    return probes + meta, not_applicable, bugs


# ===========================================================================
# 2. The driver: probe_backends() and cell_pair(), exactly run_par.py's.
# ===========================================================================

def _cell(bname: str, name: str, suffix: str, outdir: str, flake_n: int):
    backend = importlib.import_module(f"verifiers.{bname}")
    real = Path(outdir) / f"{name}.{suffix}"
    twin = Path(outdir) / f"{name}_twin.{suffix}"
    (r_real, a1), (r_twin, a2) = cell_pair(backend.verify, real, twin, flake_n)
    return name, bname, r_real.outcome, r_twin.outcome, a1 and a2


def _cell_single(bname: str, name: str, suffix: str, outdir: str,
                 flake_n: int, twin_label: str):
    """The no-twin case: a probe whose EXPECTED outcome is about the real
    program alone (harness.twin_cached found no witness), so the real body
    is still lowered and graded through the same flake_check n=3 every
    other cell uses; the twin slot carries the ladder's own refusal reason
    instead of a second kernel call."""
    backend = importlib.import_module(f"verifiers.{bname}")
    real = Path(outdir) / f"{name}.{suffix}"
    r_real, ok = flake_check(backend.verify, real, flake_n)
    return name, bname, r_real.outcome, twin_label, ok


def run_items(items: list[dict], present, outdir: Path, jobs, flake_n: int):
    """rows[name][backend] = (real_outcome, twin_outcome, agreed). Sequential
    lowering (as run_par.lower_and_dispatch), then a parallel kernel-call
    pool over whatever needed one. A "wf-refused"-expected probe, and any
    task the checker rejects unexpectedly, never reaches a kernel: SPEC.md
    gates the checker before the lowering step, and this driver matches
    that order."""
    outdir.mkdir(parents=True, exist_ok=True)
    rows = {it["name"]: {} for it in items}
    pending = []
    pending_single = []
    for it in items:
        if it["kind"] == "metamorphic-bug":
            continue
        task = it["task"]
        clean = {k: v for k, v in task.items() if not k.startswith("_")}
        name = it["name"]
        # fz_p_nodiv is deliberately fed a bare `/`, which is not a t
        # operator; fuzz_lower.build_corpus's own construction skips
        # check_wf for exactly this one name, for the same reason.
        wf_errors = [] if name == "fz_p_nodiv" else fz.check_wf(clean)
        if it["expected"] == "wf-refused":
            outcome = "wf-refused" if wf_errors else "wf-NOT-refused"
            for bname, _, _ in present:
                rows[name][bname] = (outcome, "-", True)
            continue
        if wf_errors:
            for bname, _, _ in present:
                rows[name][bname] = ("wf-error", "-", True)
            continue
        try:
            twin_body, op, w = harness.twin_cached(clean)
        except Exception as e:                                # noqa: BLE001
            # The reference interpreter refused the task outright (the
            # adversarial probe's own point). The real lowering is tried
            # alone per column: raises -> lower-error (the probe's expected
            # class), NotImplementedError -> abstain, silent accept ->
            # no-twin naming the interpreter's own reason.
            for bname, lower, suffix in present:
                try:
                    lower(clean, clean["body"])
                except NotImplementedError as e2:
                    rows[name][bname] = ("abstain", str(e2)[:120], True)
                except Exception as e2:                        # noqa: BLE001
                    rows[name][bname] = (
                        "lower-error", f"{type(e2).__name__}: {e2}"[:120], True)
                else:
                    rows[name][bname] = ("no-twin", f"interp: {e}"[:120], True)
            continue
        if twin_body is None:
            # No twin, not no real: the probe's expectation is about the
            # REAL program (harness.REFUSALS[op] is why no twin was found,
            # never a reason to skip lowering the real body itself -- see
            # the module docstring's fz_p_at_oob-shaped example).
            twin_label = f"no-twin: {harness.REFUSALS.get(op, op)}"
            for bname, lower, suffix in present:
                try:
                    real_src = lower(clean, clean["body"])
                except NotImplementedError:
                    rows[name][bname] = ("abstain", twin_label, True)
                    continue
                except Exception as e:                          # noqa: BLE001
                    rows[name][bname] = (
                        "lower-error", f"{type(e).__name__}: {e}"[:80], True)
                    continue
                rp = outdir / f"{name}.{suffix}"
                rp.write_text(real_src, encoding="utf-8", newline="\n")
                pending_single.append((bname, name, suffix, twin_label))
            continue
        for bname, lower, suffix in present:
            try:
                real_src = lower(clean, clean["body"])
                twin_src = lower(clean, twin_body, witness=w)
            except NotImplementedError:
                rows[name][bname] = ("abstain", "abstain", True)
                continue
            except Exception as e:                              # noqa: BLE001
                rows[name][bname] = (
                    "lower-error", f"{type(e).__name__}: {e}"[:120], True)
                continue
            rp = outdir / f"{name}.{suffix}"
            tp = outdir / f"{name}_twin.{suffix}"
            rp.write_text(real_src, encoding="utf-8", newline="\n")
            tp.write_text(twin_src, encoding="utf-8", newline="\n")
            pending.append((bname, name, suffix))
    n_cells = max(1, len(pending) + len(pending_single))
    jobs = jobs or max(1, min(n_cells, 8))
    ctx = mp_context()
    if pending or pending_single:
        with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx) as ex:
            futs = [ex.submit(_cell, b, n, s, str(outdir), flake_n)
                   for b, n, s in pending]
            futs += [ex.submit(_cell_single, b, n, s, str(outdir), flake_n, tl)
                    for b, n, s, tl in pending_single]
            for fut in as_completed(futs):
                name, bname, ro, to, agreed = fut.result()
                rows[name][bname] = (ro, to, agreed)
    return rows


# ===========================================================================
# 3. Grading: PASS/FAIL against the manifest's own `expected`.
# ===========================================================================

def grade(items: list[dict], rows: dict, cols: list) -> dict:
    """verdict[name][backend] in {"PASS", "FAIL", "N/A"}. N/A only for a
    backend whose kernel binary is absent (cols names it "ABSENT: ..."),
    never counted toward the suite's exit code. Grading compares the REAL
    outcome only -- metamorphic.py's own standard is verdict(T(task)) ==
    verdict(task), the base program's outcome, not a twin's; the probe
    manifest's expectation (verified/refuted/wf-refused/lower-error) is
    likewise a statement about the real lowering, per fuzz_lower.py's own
    `analyse()` (`vs_truth` compares `cells[b][0]`, never `cells[b][1]`)."""
    present_names = {b for b, v in cols if not v.startswith("ABSENT")}
    verdicts = {}
    for it in items:
        name = it["name"]
        if it["kind"] == "metamorphic-bug":
            verdicts[name] = {b: ("N/A" if b not in present_names else "FAIL")
                              for b, _ in cols}
            continue
        exp = it["expected"]
        cells = rows.get(name, {})
        per_col = {}
        for b, v in cols:
            if b not in present_names:
                per_col[b] = "N/A"
                continue
            c = cells.get(b)
            if c is None:
                per_col[b] = "FAIL"
                continue
            per_col[b] = "PASS" if c[0] == exp else "FAIL"
        verdicts[name] = per_col
    return verdicts


# ===========================================================================
# 4. CONFORMANCE.md, AGREEMENT.md's row format plus "expected" and PASS/FAIL.
# ===========================================================================

def format_table(cols, items, rows, verdicts, not_applicable, bugs,
                 outdir: Path) -> str:
    lines = [f"# t conformance suite (ROADMAP 13.4) , "
             f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}",
             "",
             "Cell = real outcome / twin outcome [PASS|FAIL|N/A]. PASS means "
             "the real outcome equals this row's `expected` column; N/A "
             "means the kernel's own binary is absent from this run (not "
             "counted toward exit code). Built from fuzz_lower.py's hand-"
             "built probes plus metamorphic.py's named TRANSFORMS applied "
             "to t/tasks/abs.t; see t/conformance.py's module docstring "
             "for the manifest.",
             ""]
    col_names = [b for b, _ in cols]
    header = "| task | expected | " + " | ".join(col_names) + " |"
    lines += [header, "|" + "---|" * (len(col_names) + 2)]
    n_fail = 0
    for it in items:
        name = it["name"]
        row = [name, it["expected"]]
        for b in col_names:
            c = rows.get(name, {}).get(b)
            v = verdicts.get(name, {}).get(b, "N/A")
            if v == "FAIL":
                n_fail += 1
            cell = "," if c is None else f"{c[0]} / {c[1]}"
            row.append(f"{cell} [{v}]")
        lines.append("| " + " | ".join(row) + " |")
    present_names = [b for b, v in cols if not v.startswith("ABSENT")]
    lines += ["", f"Kernels present: {len(present_names)} of {len(cols)} "
              f"({', '.join(present_names) if present_names else 'NONE'})"]
    lines += ["", "Backends:"] + [f"- {b}: {v}" for b, v in cols]
    lines += ["", f"Probes: {sum(1 for i in items if i['kind'] == 'probe')}"
              f"  Metamorphic: "
              f"{sum(1 for i in items if i['kind'] == 'metamorphic')}"
              f"  Tripwire bugs: {len(bugs)}"
              f"  FAIL cells: {n_fail}"]
    if not_applicable:
        lines += ["", "metamorphic.TRANSFORMS with no site in "
                  f"{BASE_TASK_PATH.name} (not silently omitted, not "
                  "graded): " + ", ".join(not_applicable)]
    ex = next((it["name"] for it in items
              if (outdir / f"{it['name']}.dfy").exists()
              and (outdir / f"{it['name']}.rs").exists()), None)
    if ex is not None:
        lines += ["", f"Verdict basis: every source file hashed; e.g. "
                  f"`{ex}.dfy` {sha256_file(outdir / f'{ex}.dfy')[:16]}…, "
                  f"`{ex}.rs` {sha256_file(outdir / f'{ex}.rs')[:16]}…"]
    else:
        lines += ["", "Verdict basis: every source file hashed."]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--flake", type=int, default=3)
    ap.add_argument("--out", type=Path, default=HERE / "CONFORMANCE.md")
    ap.add_argument("--workdir", type=Path, default=HERE / "out" / "conformance",
                    help="private directory for lowered sources, never t/out/'s"
                        " own filenames (default t/out/conformance)")
    args = ap.parse_args()

    release = acquire_run_lock(args.workdir)
    if isinstance(release, str):
        print(f"REFUSED: {release}")
        return 2
    try:
        items, not_applicable, bugs = build_manifest()
        print(f"manifest: {len(items)} tasks "
              f"({sum(1 for i in items if i['kind'] == 'probe')} probes, "
              f"{sum(1 for i in items if i['kind'] == 'metamorphic')} "
              f"metamorphic, {len(bugs)} tripwire bugs); "
              f"{len(not_applicable)} TRANSFORMS not applicable to "
              f"{BASE_TASK_PATH.name}")
        cols, present = run_par.probe_backends()
        rows = run_items(items, present, args.workdir, args.jobs, args.flake)
        verdicts = grade(items, rows, cols)
        table = format_table(cols, items, rows, verdicts, not_applicable,
                             bugs, args.workdir)
        args.out.write_text(table, encoding="utf-8", newline="\n")
        n_fail = sum(1 for it in items for b, _ in cols
                    if verdicts.get(it["name"], {}).get(b) == "FAIL")
        print(f"wrote {args.out}: {len(items)} tasks, {n_fail} FAIL cells")
        for it in items:
            for b, _ in cols:
                v = verdicts.get(it["name"], {}).get(b)
                if v == "FAIL":
                    c = rows.get(it["name"], {}).get(b)
                    print(f"  FAIL {it['name']} x {b}: expected "
                          f"{it['expected']!r}, got "
                          f"{c[0] if c else '(no cell)'!r}  [{it['kind']}]"
                          f"{'  (known kernel gap, not hidden)' if it['adversarial'] else ''}")
        return 1 if n_fail else 0
    finally:
        release()


if __name__ == "__main__":
    sys.exit(main())
