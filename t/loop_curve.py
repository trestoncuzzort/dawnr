#!/usr/bin/env python3
"""loop_curve.py -- the error curve of the t training loop, one column per
round, one row per stage, on the whole MBPP pool and on the held-out set.

The claim under test (Treston, 2026-09-09): a model trained on t verdicts
and refuted twins gets better round over round, and every failure names its
cause. This file prints the measurement, nothing else. Each column is one
tag under out/spec-experiment/<tag>/ as spec_experiment.py leaves it
(extract.json, tests.json, kernels.md); each row is a stage of that
pipeline, counted twice: over the whole pool (368 problems) and over the
problems no positive in out/loop/heldout.json came from (322), which is the
only comparison that says anything about generalisation. A stage a tag has
not reached reads "pending", never 0.

Two of the columns differ in more than the adapter: round 0 at 1.5B went
through ollama (Q4_K_M weights), rounds 1 and later through transformers
(nf4 weights, loop_generate.py), so the bare base through the transformers
path is its own column (the "r0hf" control) and the training effect is read
against that column, not against the ollama one.

    python3 loop_curve.py --tags qwen2.5-coder-1.5b qwen2.5-coder-1.5b-r0hf \\
        qwen2.5-coder-1.5b-r1 --out LOOP-CURVE.md
"""
from __future__ import annotations
import argparse
import collections
import json
import re
from pathlib import Path

import spec_experiment

HERE = Path(__file__).resolve().parent
OUT_ROOT = HERE / "out" / "spec-experiment"
HELDOUT = HERE / "out" / "loop" / "heldout.json"
_TID = re.compile(r"^mbpp_(\d+)__")


def refusal_class(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "no-block"
    if t.startswith("parse:"):
        return "parse"
    if t.startswith("wf:"):
        return "wf"
    if re.match(r"line \d+:", t):
        return "parse"
    if "no t block" in t or t == "no-block":
        return "no-block"
    return "wf"


def load_tag(tag: str) -> dict:
    d = OUT_ROOT / spec_experiment.model_tag(tag)
    out = {"tag": tag, "dir": d, "extract": {}, "tests": {}, "kcols": [], "kernels": {}}
    p = d / "extract.json"
    if p.exists():
        out["extract"] = json.loads(p.read_text(encoding="utf-8"))
    p = d / "tests.json"
    if p.exists():
        out["tests"] = json.loads(p.read_text(encoding="utf-8"))
    cols, rows = spec_experiment.parse_kernel_table(d / "kernels.md")
    out["kcols"] = cols
    for name, row in rows.items():
        m = _TID.match(name)
        if m:
            out["kernels"][m.group(1)] = row
    return out


def stages(t: dict, ids: set[str] | None) -> dict:
    """Counts for one tag over the ids given (None means every reply)."""
    ex = {k: v for k, v in t["extract"].items() if ids is None or k in ids}
    n_reply = len(ex)
    wf = {k for k, v in ex.items() if "name" in v}
    causes = collections.Counter()
    texts = collections.Counter()
    for k, v in ex.items():
        if k in wf:
            continue
        txt = v.get("refusal") or v.get("error") or v.get("why") or ""
        causes[refusal_class(txt)] += 1
        texts[re.sub(r"line \d+", "line N", txt)[:60]] += 1
    tests = {k: v for k, v in t["tests"].items() if k in wf}
    t_pass = sum(1 for v in tests.values() if v.get("overall") == "pass")
    kern = {k: t["kernels"][k] for k in wf if k in t["kernels"]}
    cols = t["kcols"]
    reached = len(kern) if cols else None
    some = sum(1 for r in kern.values() if any(r.get(c) == "verified / refuted" for c in cols)) if cols else None
    seven = sum(1 for r in kern.values() if cols and all(r.get(c) == "verified / refuted" for c in cols)) if cols else None
    both = (sum(1 for k, r in kern.items() if all(r.get(c) == "verified / refuted" for c in cols)
                and tests.get(k, {}).get("overall") == "pass") if cols else None)
    both_some = (sum(1 for k, r in kern.items() if any(r.get(c) == "verified / refuted" for c in cols)
                     and tests.get(k, {}).get("overall") == "pass") if cols else None)
    per_kernel = {c: sum(1 for r in kern.values() if r.get(c) == "verified / refuted") for c in cols}
    return {"replies": n_reply, "well-formed": len(wf), "tests pass": t_pass,
            "reached the kernels": reached,
            "verified with a refuted twin, some column": some,
            "verified with a refuted twin, all seven": seven,
            "all seven and tests pass": both,
            "some column and tests pass": both_some,
            "causes": causes, "texts": texts, "per_kernel": per_kernel}


ROWS = ["replies", "well-formed", "tests pass", "reached the kernels",
        "verified with a refuted twin, some column",
        "verified with a refuted twin, all seven",
        "some column and tests pass", "all seven and tests pass"]


def fmt(v) -> str:
    return "pending" if v is None else str(v)


def render(tags: list[dict], held: set[str], used: set[str]) -> str:
    L = []
    L.append("# The t loop's error curve, 1.5B, 2026-09-09")
    L.append("")
    L.append("Generated by `t/loop_curve.py`. One column per round, one row per stage of")
    L.append("`spec_experiment.py`'s pipeline; a stage not yet run reads pending. Read the")
    L.append("training effect between the two transformers-path columns (the bare base")
    L.append("and the adapter), not against the ollama column, whose weights are a")
    L.append("different quantisation. Positives for the adapter came from the 7B's round 0")
    L.append("and the lifted MBPP-DFY tasks; the held-out set is every pool problem none of")
    L.append("them touched.")
    L.append("")
    names = [t["tag"] for t in tags]
    for title, ids in (("## Whole pool (%d problems)" % len(tags[0]["extract"] or held | used), None),
                       ("## Held out (%d problems no positive came from)" % len(held), held),
                       ("## Used in training (%d problems a positive came from)" % len(used), used)):
        L.append(title)
        L.append("")
        st = [stages(t, ids) for t in tags]
        L.append("| stage | " + " | ".join(names) + " |")
        L.append("|---|" + "---:|" * len(names))
        for r in ROWS:
            L.append(f"| {r} | " + " | ".join(fmt(s[r]) for s in st) + " |")
        L.append("")
        L.append("Refusals at extract, by cause:")
        L.append("")
        L.append("| cause | " + " | ".join(names) + " |")
        L.append("|---|" + "---:|" * len(names))
        for c in ("parse", "wf", "no-block"):
            L.append(f"| {c} | " + " | ".join(str(s['causes'].get(c, 0)) for s in st) + " |")
        L.append("")
        if ids is None:
            L.append("Per kernel, verified with a refuted twin (over the well-formed tasks):")
            L.append("")
            cols = sorted({c for t in tags for c in t["kcols"]})
            L.append("| kernel | " + " | ".join(names) + " |")
            L.append("|---|" + "---:|" * len(names))
            for c in cols:
                L.append(f"| {c} | " + " | ".join(("pending" if not t["kcols"] else str(s["per_kernel"].get(c, 0)))
                                                  for t, s in zip(tags, st)) + " |")
            L.append("")
            L.append("Most frequent refusal texts (line numbers folded):")
            L.append("")
            for t, s in zip(tags, st):
                L.append(f"- {t['tag']}: " + "; ".join(f"{n} x `{txt}`" for txt, n in s["texts"].most_common(5)))
            L.append("")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tags", nargs="+", required=True)
    ap.add_argument("--out", type=Path, default=HERE / "LOOP-CURVE.md")
    ap.add_argument("--heldout", type=Path, default=HELDOUT)
    args = ap.parse_args(argv)
    h = json.loads(args.heldout.read_text(encoding="utf-8"))
    held = {str(x) for x in h.get("heldout_task_ids", h.get("heldout", []))}
    used = {str(x) for x in h.get("used_task_ids", h.get("used", []))}
    tags = [load_tag(t) for t in args.tags]
    text = render(tags, held, used)
    args.out.write_text(text, encoding="utf-8")
    print(text.split("\n## Held out")[0])
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
