#!/usr/bin/env python3
"""sweepdiff.py <old COVERAGE-lifted-785.md> <new>: cell-by-cell comparison of two
sweep tables. Prints headline counts (rows, all-seven overall and on the
dafny_synthesis rows), per-kernel transition counts for rows in both tables,
every real that changed (a real leaving verified is the wrong way), the new
rows with their all-seven status, and the new table's sole-blockers section."""
import sys
from collections import Counter

K = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]


def parse(path):
    rows, sole = {}, []
    in_sole = False
    for line in open(path):
        if line.startswith("## Sole blockers"):
            in_sole = True
        if in_sole:
            sole.append(line.rstrip("\n"))
            continue
        if not line.startswith("| ") or line.startswith("| task") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.rstrip("\n").split("|")[1:-1]]
        if len(cells) != 8:
            continue
        rows[cells[0]] = dict(zip(K, cells[1:]))
    return rows, sole


def all7(cells):
    return all(v == "verified / refuted" for v in cells.values())


old, _ = parse(sys.argv[1])
new, sole = parse(sys.argv[2])
ds = lambda rows: {r: c for r, c in rows.items() if r.startswith("dafny_synthesis_task_id_")}
for name, rows in (("old", old), ("new", new)):
    d = ds(rows)
    print(f"{name}: rows {len(rows)}, all-seven {sum(all7(c) for c in rows.values())}; "
          f"dafny_synthesis rows {len(d)}, all-seven {sum(all7(c) for c in d.values())}")
common = sorted(set(old) & set(new))
print(f"rows in both {len(common)}, new rows {len(set(new) - set(old))}, gone rows {len(set(old) - set(new))}")
trans = {k: Counter() for k in K}
real_moved, touched = [], set()
for r in common:
    for k in K:
        a, b = old[r][k], new[r][k]
        if a != b:
            trans[k][(a, b)] += 1
            touched.add(r)
            ra, rb = a.split(" / ")[0], b.split(" / ")[0]
            if ra != rb:
                real_moved.append((r, k, a, b))
print(f"rows touched {len(touched)}")
for k in K:
    if trans[k]:
        print(f"  {k}:")
        for (a, b), n in trans[k].most_common():
            print(f"    {n:3d}  {a}  ->  {b}")
print("reals that moved (a real leaving verified is the wrong way):")
for r, k, a, b in real_moved:
    flag = "WRONG WAY" if a.startswith("verified") and not b.startswith("verified") else ""
    print(f"  {r} x {k}: {a} -> {b} {flag}")
print("twins that moved away from refuted:")
for r in common:
    for k in K:
        a, b = old[r][k], new[r][k]
        if a.endswith("/ refuted") and not b.endswith("/ refuted") and a != b:
            print(f"  {r} x {k}: {a} -> {b}")
print("new rows:")
for r in sorted(set(new) - set(old)):
    c = new[r]
    bad = [f"{k}={v}" for k, v in c.items() if v != "verified / refuted"]
    print(f"  {r}: {'ALL SEVEN' if all7(c) else ', '.join(bad)}")
print("\n".join(sole))
