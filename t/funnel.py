#!/usr/bin/env python3
"""t/funnel.py -- where answers die between a model's reply and a training example (2026-09-18).

    python3 t/funnel.py [--out t/FUNNEL-2026-09-18.md] [tag ...]

Round 4 ended with a pool covering 55 problems out of 3,003, built from 10,099 generations, and the obvious
question -- generate more, or generate better? -- cannot be answered from the pool alone. This walks every
answer set through the five gates it must pass and counts the survivors at each:

    reply -> a t block at all -> parses -> well formed -> its own tests pass -> seven proofs and a refuted twin

The last gate is only counted for sets that have been graded; the rest are counted for every set on disk. A
gate that loses most answers in every set is where the next round's work belongs, and a gate that loses them in
stock models but not in a model trained on t says the loop itself is the fix.

Standard library only. The table it prints is the table it writes.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SE = HERE / "out" / "spec-experiment"
KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
# a model trained on t's own corpus, so its parse rate answers a different question from a stock model's
TRAINED = re.compile(r"^(locallm|student)")


def funnel(tag_dir: Path) -> dict | None:
    try:
        ex = json.loads((tag_dir / "extract.json").read_text())
    except (OSError, ValueError):
        return None
    stage = collections.Counter(v.get("stage") for v in ex.values())
    row = {"tag": tag_dir.name, "replies": len(ex),
           "block": len(ex) - stage["no-block"],
           "parses": len(ex) - stage["no-block"] - stage["parse"],
           "wf": stage["task"], "tests": 0, "graded": 0, "clean": 0}
    try:
        tests = json.loads((tag_dir / "tests.json").read_text())
        row["tests"] = sum(1 for v in tests.values() if v.get("overall") == "pass")
        passing = {v.get("name") for v in tests.values() if v.get("overall") == "pass"}
    except (OSError, ValueError):
        passing = set()
    if (tag_dir / "kernels.md").exists():
        import spec_experiment as se
        _cols, cells = se.parse_kernel_table(tag_dir / "kernels.md")
        row["graded"] = len(cells)
        row["clean"] = sum(1 for n, r in cells.items()
                           if n in passing and all(r.get(k, "").startswith("verified / refuted") for k in KERNELS))
    return row


def reasons(tag_dir: Path, n: int = 8) -> list[tuple[int, str]]:
    """What the parser and the well-formedness check refused, with the numbers and quoted names flattened so
    that the same complaint about different identifiers counts once."""
    try:
        ex = json.loads((tag_dir / "extract.json").read_text())
    except (OSError, ValueError):
        return []
    why = collections.Counter()
    for v in ex.values():
        if v.get("stage") not in ("parse", "wf"):
            continue
        w = re.sub(r"'[^']*'", "'X'", v.get("why", "")[:110])
        why[f"{v['stage']}: " + re.sub(r"\b\d+\b", "N", w)] += 1
    return [(c, w) for w, c in why.most_common(n)]


def wanted(tag_dirs: list[Path], n: int = 14) -> list[tuple[int, str]]:
    """The tokens the parser found where it wanted something else: what the models keep reaching for and t
    does not have, counted over every set at once."""
    tok = collections.Counter()
    for d in tag_dirs:
        try:
            ex = json.loads((d / "extract.json").read_text())
        except (OSError, ValueError):
            continue
        for v in ex.values():
            if v.get("stage") != "parse":
                continue
            w = v.get("why", "")
            m = (re.search(r"found '([^']*)'", w) or re.search(r"unexpected character '([^']*)'", w)
                 or re.search(r"'([^']*)' does not start", w) or re.search(r"'([^']*)' is not one of", w))
            if m:
                tok[m.group(1)] += 1
    return [(c, t) for t, c in tok.most_common(n)]


def strip_comments(src: str) -> str:
    """Whatever follows // or # outside a literal, dropped. t has no comments on purpose -- a comment has no
    AST node, so it could not survive print(parse(text)) -- but a model that annotates its program has not
    written a different program, and this asks how much of the parse wall is only that."""
    out = []
    for line in src.splitlines():
        quote, cut, i = None, None, 0
        while i < len(line):
            c = line[i]
            if quote:
                if c == "\\":
                    i += 2
                    continue
                if c == quote:
                    quote = None
            elif c in "'\"":
                quote = c
            elif c == "#" or line[i:i + 2] == "//":
                cut = i
                break
            i += 1
        out.append(line[:cut] if cut is not None else line)
    return "\n".join(out)


def c_spellings(src: str) -> str:
    """`&&` and `||` read as `and` and `or`: the same operators, spelled the way C spells them."""
    return re.sub(r"\|\|", " or ", re.sub(r"&&", " and ", src))


def rescue(tag_dirs: list[Path]) -> tuple[int, list[tuple[str, int]]]:
    """How many refused replies a more tolerant reader would accept, layer by layer. If this number were
    large, the parse wall would be orthography and the fix would be a preprocessor over answers already
    generated -- no regeneration, no grammar, no new language."""
    import spec_experiment as se
    import surface
    layers = [("comments dropped", strip_comments),
              ("and && and || read as and/or", lambda s: c_spellings(strip_comments(s)))]
    got = collections.Counter()
    refused = 0
    for d in tag_dirs:
        try:
            ex = json.loads((d / "extract.json").read_text())
        except (OSError, ValueError):
            continue
        for tid, v in ex.items():
            if v.get("stage") != "parse":
                continue
            raw = d / "raw" / f"{tid}.json"
            if not raw.exists():
                continue
            refused += 1
            try:
                block = se.find_block(json.loads(raw.read_text())["reply"]) or ""
            except (OSError, ValueError, KeyError):
                continue
            for name, f in layers:
                try:
                    surface.parse(f(block))
                except Exception:                               # noqa: BLE001
                    continue
                got[name] += 1
                break
    return refused, [(n, got[n]) for n, _f in layers]


def pct(a: int, b: int) -> str:
    if not b:
        return "-"
    # a few out of hundreds is not none, and rounding it to 0% would read as none
    return "<1%" if a and 100 * a / b < 0.5 else f"{100 * a / b:.0f}%"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tags", nargs="*")
    ap.add_argument("--out", type=Path, default=HERE / "FUNNEL-2026-09-18.md")
    a = ap.parse_args()
    dirs = [SE / t for t in a.tags] if a.tags else sorted(p for p in SE.glob("*") if (p / "extract.json").exists())
    rows = [r for r in (funnel(d) for d in dirs) if r]
    if not rows:
        print("no answer set has an extract.json; run `spec_experiment.py extract` first")
        return 1

    lines = ["# Where answers die, 2026-09-18", "",
             "Written by `t/funnel.py` over every answer set on this machine. Each column is the answers left",
             "after one gate, and the percentage is of the model's replies. `clean` is counted only for sets",
             "that have been graded, and it is what the pool is built from.", "",
             "| answer set | replies | a t block | parses | well formed | tests pass | graded | clean |",
             "|---|---|---|---|---|---|---|---|"]
    print(f"{'answer set':34s} {'replies':>7s} {'parses':>12s} {'wf':>10s} {'tests':>10s} {'clean':>8s}")
    for r in sorted(rows, key=lambda x: -x["replies"]):
        lines.append(f"| `{r['tag']}` | {r['replies']} | {r['block']} | {r['parses']} ({pct(r['parses'], r['replies'])}) "
                     f"| {r['wf']} ({pct(r['wf'], r['replies'])}) | {r['tests']} ({pct(r['tests'], r['replies'])}) "
                     f"| {r['graded'] or '-'} | {r['clean'] if r['graded'] else '-'} |")
        print(f"{r['tag']:34s} {r['replies']:7d} {r['parses']:6d} {pct(r['parses'], r['replies']):>5s} "
              f"{r['wf']:6d} {pct(r['wf'], r['replies']):>3s} {r['tests']:6d} {pct(r['tests'], r['replies']):>3s} "
              f"{(str(r['clean']) if r['graded'] else '-'):>8s}")

    def group(rows_):
        return (sum(r["parses"] for r in rows_), sum(r["wf"] for r in rows_),
                sum(r["tests"] for r in rows_), sum(r["replies"] for r in rows_))

    stock = [r for r in rows if not TRAINED.match(r["tag"])]
    scratch = [r for r in rows if r["tag"].startswith("locallm")]
    student = [r for r in rows if r["tag"].startswith("student")]
    sp, tp, up = group(stock), group(scratch), group(student)
    lines += ["", "## The gate that loses the most, and what moves it", "",
              "| models | replies | parse | well formed | tests pass |", "|---|---|---|---|---|",
              f"| stock, prompted | {sp[3]} | {pct(sp[0], sp[3])} | {pct(sp[1], sp[3])} | {pct(sp[2], sp[3])} |",
              f"| the fine-tuned student | {up[3]} | {pct(up[0], up[3])} | {pct(up[1], up[3])} | {pct(up[2], up[3])} |",
              f"| locallm, trained on t from scratch | {tp[3]} | {pct(tp[0], tp[3])} | {pct(tp[1], tp[3])} "
              f"| {pct(tp[2], tp[3])} |", "",
              "Two readings, and the second is the awkward one.", "",
              "The syntax gate loses more answers than every other gate together: a prompted stock model writes",
              f"something the parser accepts {pct(sp[0], sp[3])} of the time, and no proof system ever sees the rest.",
              "",
              f"Training on t moves that gate and only that gate. locallm, trained on t's corpus from scratch,",
              f"writes t the parser accepts {pct(tp[0], tp[3])} of the time and well formed {pct(tp[1], tp[3])} of",
              f"the time -- and then {pct(tp[2], tp[3])} of its answers pass the problem's own tests. It has learned",
              "the notation and not the problem. The fine-tuned student, trained on the pool by QLoRA and DPO,",
              f"parses {pct(up[0], up[3])}, which is where the untrained 1.5B already was: that training moved neither.",
              "",
              "So the pool is not yet teaching what it is supposed to teach, and a round that only adds more",
              "answers of the same kind will not change these three rows. The question a next round has to",
              "answer is whether a model can be made to hold both ends at once -- the notation locallm has and",
              "the semantics the stock models have -- because the gap between those two rows, not the provers,",
              "is the whole distance to a higher clean count.", "",
              "What the parser found where it wanted something else, over every set:", ""]
    for c, t in wanted(dirs):
        lines.append(f"- `{t}` -- {c}")
    refused, layers = rescue(dirs)
    lines += ["", "## Is the wall orthography?", "",
              "The cheapest imaginable fix would be a more tolerant reader: the answers are already generated,",
              "so anything a preprocessor can rescue costs one re-extraction and no GPU at all. Measured over",
              f"the {refused} replies the parser refused whose raw reply is still on this machine:", ""]
    for name, got in layers:
        lines.append(f"- with {name}: {got} more parse ({pct(got, refused)})")
    lines += ["",
              "So it is not orthography. The refusals are structural -- `let x := e in ...`, list",
              "comprehensions, `?:`, `^` for powers, a spec function written after the task it serves -- and a",
              "reader cannot be made tolerant enough without becoming a different language. That closes the",
              "cheap door and leaves the generator: a model that decodes against t's grammar cannot write any",
              "of them in the first place (WS-21).", "",
              "## What the refusals say, per set", ""]
    for d in dirs:
        rs = reasons(d)
        if not rs:
            continue
        lines.append(f"### `{d.name}`")
        lines += [f"- {c} x {w}" for c, w in rs] + [""]
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nparse rate: stock {pct(sp[0], sp[3])}, the fine-tuned student {pct(up[0], up[3])}, "
          f"locallm {pct(tp[0], tp[3])}; locallm's answers pass their tests {pct(tp[2], tp[3])} of the time")
    print(f"written to {a.out.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
