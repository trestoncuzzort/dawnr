#!/usr/bin/env python3
"""t/twins_artifact.py -- the twins and their witnesses as a thing you can hold (2026-09-19, WS-20 move 4).

    python3 t/twins_artifact.py [--out t/twins] [--pairs t/out/loop] [--check]

A pile of verified programs can be had from any corpus. What this project has and others do not is a verified
program **paired with a near-miss** -- one deliberate edit away -- **and the concrete input that separates
them**, with seven independent proof systems on record refuting the near-miss at that input.

Until now that lived as a by-product: the operator and the witness inside the loop's pair files, the seven
verdicts inside a kernels.md, the programs inside an answer set nobody outside this repository has. This
writes it out as one file per pair, with an index, a count and a licence line, versioned like AGREEMENT.md.

A pair is written only when both halves are on the record: the real program verified in all seven, and the
twin refuted in all seven. Anything weaker is left out rather than shipped with a footnote.

`--check` writes nothing and exits non-zero if the artifact on disk is not what this would write, which is the
form for a test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
FENCE = re.compile(r"```t\n(.*?)```", re.S)


def unfence(text: str) -> str:
    m = FENCE.search(text or "")
    return (m.group(1) if m else (text or "")).strip()


def witness_sentence(w: dict) -> str:
    """The witness as a line a person can read: what was passed in, what each program answered."""
    if not isinstance(w, dict):
        return ""
    args = ", ".join(f"{k}={json.dumps(v)}" for k, v in sorted(w.items()) if not k.startswith("_"))
    real, twin = w.get("_real"), w.get("_twin")
    if w.get("_kind") == "value":
        return f"at {args} the program answers {json.dumps(real)} and the twin answers {json.dumps(twin)}"
    return f"at {args} the twin breaks the specification the program keeps"


def collect(pairs_dir: Path) -> list[dict]:
    """Every pair whose real half verified in all seven and whose twin was refuted by all seven."""
    seen, out = set(), []
    for path in sorted(pairs_dir.glob("pairs-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not str(r.get("kind", "")).startswith("twin:"):
                continue                                        # only deliberate twins, not other negatives
            refuted = set(r.get("refuted_kernels") or [])
            if r.get("kernel_count") != len(KERNELS) or refuted != set(KERNELS):
                continue                                        # one half not on the record: leave it out
            real, twin = unfence(r.get("chosen")), unfence(r.get("rejected"))
            if not real or not twin or real == twin:
                continue
            key = hashlib.sha256((real + "\0" + twin).encode("utf-8")).hexdigest()[:16]
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "id": key,
                "task": r.get("task"),
                "problem": r.get("task_id"),
                "operator": r.get("operator"),
                "written_by": r.get("tag"),
                "program": real,
                "twin": twin,
                "witness": r.get("witness"),
                "witness_reads": witness_sentence(r.get("witness") or {}),
                "verified_by": sorted(KERNELS),
                "twin_refuted_by": sorted(refuted),
            })
    return sorted(out, key=lambda d: (str(d["task"]), d["id"]))


def render(rows: list[dict]) -> dict[str, str]:
    """Path -> contents, for everything the artifact is made of."""
    files = {f"pairs/{r['task']}.{r['id']}.json": json.dumps(r, indent=1, sort_keys=True) + "\n" for r in rows}
    ops: dict[str, int] = {}
    for r in rows:
        ops[str(r["operator"])] = ops.get(str(r["operator"]), 0) + 1
    index = ["task\tproblem\toperator\twritten by\tfile"]
    index += [f"{r['task']}\t{r['problem']}\t{r['operator']}\t{r['written_by']}\tpairs/{r['task']}.{r['id']}.json"
              for r in rows]
    files["INDEX.tsv"] = "\n".join(index) + "\n"
    files["README.md"] = "\n".join([
        "# t twins: verified programs paired with the near-miss that breaks them", "",
        f"{len(rows)} pairs. Written by `t/twins_artifact.py`; regenerate with `python3 t/twins_artifact.py`",
        "and check an unchanged tree with `--check`.", "",
        "Each file under `pairs/` holds one pair:", "",
        "- `program`: a task in t -- a program with its own specification -- that passed the problem's own",
        "  tests and was **verified by all seven** proof systems (Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq,",
        "  F\\*).",
        "- `twin`: the same program with one deliberate edit, named in `operator`.",
        "- `witness`: the concrete input at which the twin breaks the specification the program keeps, with",
        "  what each one answers there. `witness_reads` says it in a sentence.",
        "- `twin_refuted_by`: the seven systems that refuted the twin. A pair is written only when both halves",
        "  are on the record -- verified in all seven and refuted in all seven -- so there is no pair here",
        "  resting on a partial column.", "",
        "## Why this and not a corpus of verified programs", "",
        "Verified programs are abundant. A verified program *and* a near-miss *and* the input that separates",
        "them *and* seven independent refutations of the near-miss at that input is the part with no",
        "substitute: it is what lets a model be trained, or graded, on the difference between a proof that",
        "holds and one that does not, rather than on proofs alone.", "",
        "## The operators that made the twins", "",
        "| operator | pairs |", "|---|---|",
        *[f"| `{k}` | {v} |" for k, v in sorted(ops.items(), key=lambda kv: -kv[1])], "",
        "## Provenance", "",
        "Every pair came from a model's answer to a problem in `nl/`, filtered by the problem's own tests and",
        "by the seven, and recorded by `t/loop_dataset.py`. `written_by` names the answer set. The verdicts",
        "are the same runs `t/AGREEMENT.md` and each set's `kernels.md` record.", "",
        "## Licence", "",
        "Research and education only, as the repository's [`LICENSE`](../../LICENSE) states; commercial use,",
        "and training a model on this artifact outside research, need written permission.", "",
    ])
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=HERE / "twins")
    ap.add_argument("--pairs", type=Path, default=HERE / "out" / "loop")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    rows = collect(a.pairs)
    if not rows:
        print(f"no pair in {a.pairs} has both halves on the record; nothing written")
        return 1
    files = render(rows)

    if a.check:
        bad = []
        for rel, text in files.items():
            p = a.out / rel
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                bad.append(rel)
        extra = [str(p.relative_to(a.out)) for p in a.out.rglob("*")
                 if p.is_file() and str(p.relative_to(a.out)) not in files]
        if bad or extra:
            print(f"the artifact is not what the pairs say it should be: "
                  f"{len(bad)} file(s) differ or are missing, {len(extra)} left over")
            for rel in (bad + extra)[:5]:
                print(f"  {rel}")
            return 1
        print(f"{len(rows)} pairs, artifact matches the pair files")
        return 0

    for rel, text in files.items():
        p = a.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    ops = len({r["operator"] for r in rows})
    tasks = len({r["task"] for r in rows})
    print(f"{len(rows)} pairs over {tasks} programs, {ops} twin operators, written to "
          f"{a.out.relative_to(HERE.parent)} at {time.strftime('%Y-%m-%d %H:%MZ', time.gmtime())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
