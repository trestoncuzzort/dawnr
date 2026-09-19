#!/usr/bin/env python3
"""lowerprobe.py <task.json>: twin_for plus all seven lowerings (real and twin),
no kernel. One line: name, twin op, per-kernel seconds for real/twin, peak RSS.
Crashes and refusals are named inline. Run under a memory cap and a clock."""
import sys, time, resource, os
sys.path.insert(0, "$HOME/tup/t")
import tasks_io, harness
task = tasks_io.load_task(sys.argv[1])
name = task.get("name")
t0 = time.time()
try:
    body, op, w = harness.twin_for(task)
except Exception as e:
    print(f"{name} twin_for CRASH {type(e).__name__}: {str(e)[:120]}", flush=True); body, op, w = None, None, None
tw = time.time() - t0
cells = []
for k in ("dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"):
    mod = __import__("lower_" + k)
    for label, b, wit in (("real", task["body"], None), ("twin", body, w)):
        if b is None:
            continue
        t1 = time.time()
        try:
            src = mod.lower(task, b, witness=wit); res = f"{len(src)}"
        except NotImplementedError as e:
            res = "refused"
        except Exception as e:
            res = "CRASH:" + type(e).__name__
        cells.append(f"{k}.{label[0]}={res}/{time.time()-t1:.1f}s")
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
print(f"{name} op={op} twin_for={tw:.1f}s rss={rss:.2f}GB " + " ".join(cells), flush=True)
