"""Copy into <dir>/grade-in only the tasks that pass their tests and are not an
exact copy (canonical AST, name erased) of a task already picked in an earlier
set; the keys persist in keys.txt beside this script."""
import copy, json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "tup/t"))
import spec_experiment as se, surface
d = Path(sys.argv[1]); keysf = Path(__file__).with_name("keys.txt")
seen = set(keysf.read_text().splitlines()) if keysf.exists() else set()
out = d / "grade-in"; out.mkdir(exist_ok=True)
tests = json.loads((d / "tests.json").read_text())
n = kept = 0
for v in tests.values():
    if v.get("overall") != "pass":
        continue
    n += 1
    f = d / "tasks" / f"{v['name']}.json"
    task = json.loads(f.read_text())
    k = surface.canon(se.rename_task(copy.deepcopy(task), "x_task"))
    if k in seen:
        continue
    seen.add(k); kept += 1
    shutil.copy(f, out / f.name)
keysf.write_text("\n".join(sorted(seen)))
print(f"{d.name}: {n} pass their tests, {kept} new")
