#!/usr/bin/env python3
"""t/udebug_bank.py -- the task bank from a judge's stored input/output export (2026-10-12).

    python3 t/udebug_bank.py --corpus t/out/udebug-bulk-20261011 --uva-text PATH/problem_statements/uva_text \
        --out t/out/udebug/bank.jsonl [--judges UVa,URI] [--hand-solved problems/uva]

The export (not committed: the judge's data is private research data, the statements are the
publishers') holds, per problem, the judge's stored cases as `udebug_in/<judge>/<id>/NNNN.in.txt`
and `NNNN.out.txt` -- the layout `t/judge.py` reads -- and, where the publisher's statement was
collected, its text. This module joins the two into one record per problem so a generator can be
prompted (statement, a sample case) and its answer judged (every stored case), the setting of
ReST-EM (arXiv:2312.06585): a binary test oracle per problem, sample, keep what passes, fine-tune
once from the base model. What ReST-EM reports going wrong -- "more iterations lead to a regression"
from "overfitting on the small set of training problems" -- is why the bank records a held-out
split by hash and why the hand-solved problems (`t/PREDICT-2026-10-08-math.md`'s measured set) are
marked and never trained on.

A record:
    judge, id, url, title            from the catalog
    statement                        the publisher's text, or null when it was not collected
    n_files, n_scored                stored cases; a case whose output is uDebug's placeholder
                                     "Sorry! Output limit exceeded!" has no stored output and is
                                     not scored (judge.py skips it the same way)
    in_bytes, out_bytes              totals over the scored cases
    io_shape                         "int" when every whitespace token of every scored input and
                                     output is an integer (the t tasks of the measured set are all
                                     of this shape), else "text"
    sample_in, sample_out            the smallest scored case, each truncated
    hand_solved                      the problem has a t solution in --hand-solved (held out)
    split                            "heldout" for the hash held-out fraction (--heldout-frac,
                                     --split-seed), else "train"

Nothing here calls a model. Measured on the export of 2026-10-12: see the summary this prints and
writes beside --out.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PLACEHOLDER = "Sorry! Output limit exceeded!"
INT_TOKEN = re.compile(r"^[+-]?\d+$")
TOKEN_SCAN_BYTES = 65536


def catalog(corpus: Path) -> dict[tuple[str, str], dict]:
    out = {}
    with (corpus / "catalog.jsonl").open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            out[(r["judge"], str(r["id"]))] = r
    return out


def statement_for(corpus: Path, uva_text: Path | None, judge: str, ident: str, url: str) -> str | None:
    """UVa statements are the publisher's PDFs converted to text, bucketed by thousand
    (`<uva-text>/0000-0999/495.txt`); every other judge's statement sits under
    `<corpus>/statements/<judge>/<sha256(url)[:16]>/statement.txt`, the collector's own layout."""
    if judge == "UVa":
        if uva_text is None or not ident.isdigit():
            return None
        low = int(ident) // 1000 * 1000
        p = uva_text / f"{low:04d}-{low + 999:04d}" / f"{ident}.txt"
    else:
        p = corpus / "statements" / judge / hashlib.sha256(url.encode()).hexdigest()[:16] / "statement.txt"
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8", errors="replace").strip()
    return text or None


def io_shape(paths: list[Path]) -> str:
    for p in paths:
        with p.open("rb") as f:
            head = f.read(TOKEN_SCAN_BYTES).decode("utf-8", errors="replace")
        for tok in head.split():
            if not INT_TOKEN.match(tok):
                return "text"
    return "int"


def truncate(p: Path, limit: int) -> str:
    text = p.read_text(encoding="utf-8", errors="replace")
    return text if len(text) <= limit else text[:limit] + f"\n...[{len(text) - limit} more characters]"


def hand_solved_ids(directory: Path | None) -> set[str]:
    if directory is None:
        return set()
    return {p.stem[1:] for p in directory.glob("p*.t") if p.stem[1:].isdigit()}


def split_of(judge: str, ident: str, seed: int, frac: float) -> str:
    h = hashlib.sha256(f"{seed}:{judge}/{ident}".encode()).digest()
    return "heldout" if int.from_bytes(h[:4], "big") / 2**32 < frac else "train"


def build(corpus: Path, uva_text: Path | None, judges: set[str] | None, hand: set[str],
          seed: int, frac: float, sample_chars: int):
    cat = catalog(corpus)
    root = corpus / "udebug_in"
    records = []
    summary: dict[str, dict] = {}
    for judge_dir in sorted(root.iterdir()):
        judge = judge_dir.name
        if judges and judge not in judges:
            continue
        s = summary.setdefault(judge, {"problems": 0, "with_statement": 0, "int_shaped": 0,
                                       "files": 0, "scored": 0, "hand_solved": 0, "heldout": 0})
        for pdir in sorted(judge_dir.iterdir()):
            ins = sorted(pdir.glob("*.in.txt"))
            if not ins:
                continue
            ident = pdir.name
            rec = cat.get((judge, ident), {})
            url = rec.get("url") or f"https://www.udebug.com/{judge}/{ident}"
            scored = []
            for i in ins:
                o = i.with_name(i.name.replace(".in.txt", ".out.txt"))
                if not o.is_file():
                    continue
                if o.read_text(encoding="utf-8", errors="replace").strip() == PLACEHOLDER:
                    continue
                scored.append((i, o))
            s["problems"] += 1
            s["files"] += len(ins)
            s["scored"] += len(scored)
            statement = statement_for(corpus, uva_text, judge, ident, url)
            s["with_statement"] += statement is not None
            shape = io_shape([p for pair in scored for p in pair]) if scored else "text"
            s["int_shaped"] += shape == "int"
            is_hand = judge == "UVa" and ident in hand
            s["hand_solved"] += is_hand
            split = "measured" if is_hand else split_of(judge, ident, seed, frac)
            s["heldout"] += split == "heldout"
            smallest = min(scored, key=lambda pair: pair[0].stat().st_size) if scored else None
            records.append({
                "judge": judge, "id": ident, "url": url, "title": rec.get("title"),
                "statement": statement,
                "n_files": len(ins), "n_scored": len(scored),
                "in_bytes": sum(i.stat().st_size for i, _ in scored),
                "out_bytes": sum(o.stat().st_size for _, o in scored),
                "io_shape": shape,
                "sample_in": truncate(smallest[0], sample_chars) if smallest else None,
                "sample_out": truncate(smallest[1], sample_chars) if smallest else None,
                "tests_dir": str(pdir.relative_to(corpus)),
                "hand_solved": is_hand, "split": split,
            })
    return records, summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", required=True, help="the export: catalog.jsonl, udebug_in/, statements/")
    ap.add_argument("--uva-text", default="", help="bucketed UVa statement text, <low>-<high>/<id>.txt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--judges", default="", help="comma-separated judges (default: all present)")
    ap.add_argument("--hand-solved", default="", help="directory of p<id>.t solutions to hold out as measured")
    ap.add_argument("--split-seed", type=int, default=1338)
    ap.add_argument("--heldout-frac", type=float, default=0.1)
    ap.add_argument("--sample-chars", type=int, default=600)
    a = ap.parse_args(argv)
    corpus = Path(a.corpus)
    judges = {j.strip() for j in a.judges.split(",") if j.strip()} or None
    records, summary = build(corpus, Path(a.uva_text) if a.uva_text else None, judges,
                             hand_solved_ids(Path(a.hand_solved) if a.hand_solved else None),
                             a.split_seed, a.heldout_frac, a.sample_chars)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    total = {k: sum(s[k] for s in summary.values()) for k in next(iter(summary.values()))} if summary else {}
    report = {"records": len(records), "by_judge": summary, "total": total,
              "split_seed": a.split_seed, "heldout_frac": a.heldout_frac}
    out.with_name(out.stem + "-summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
