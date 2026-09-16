#!/usr/bin/env python3
"""install26.py: fold relift26 (the bulk 164 under the gate's load) and relift26b
(the seven re-lifted alone) into t/out/lift through install_relift.py. A stem
whose fresh outcome carries a load timeout (resolve-failure timeout, or a
lift-diff-failed 'timeout' refusal) is skipped and named, so the reference
entry stays as it was rather than being replaced by a timeout."""
import json, shutil, subprocess, sys
from pathlib import Path

S = Path("/tmp/claude-1004/-home-tmcuzzort/2118453c-5ae7-47ef-9be5-9ab0b2538b3d/scratchpad")
bulk, alone, dest = S / "relift26", S / "relift26b", S / "relift26-install"
seven = {l.strip()[:-len(".dfy")] for l in open(S / "wave-p-merge/relift7.txt") if l.strip()}


def timed_out(d, stem):
    o = json.load(open(d / f"{stem}.outcome.json"))
    rr = o.get("resolve_refusal") or {}
    if "timeout" in str(rr.get("token", "")):
        return True
    for m in o.get("methods", []):
        r = m.get("refusal") or {}
        if r.get("reason") == "lift-diff-failed" and r.get("token") == "timeout":
            return True
    return False


if dest.exists():
    shutil.rmtree(dest)
dest.mkdir()
skipped, installed = [], 0
for stem in sorted(f.name[: -len(".outcome.json")] for f in bulk.glob("*.outcome.json")):
    src = alone if stem in seven else bulk
    if not (src / f"{stem}.outcome.json").exists():
        skipped.append((stem, "no outcome in " + src.name)); continue
    if timed_out(src, stem):
        skipped.append((stem, "timeout in " + src.name)); continue
    for f in src.glob(stem + ".*"):
        if f.is_file():
            shutil.copy2(f, dest / f.name)
    installed += 1
print("staged", installed, "programs; skipped (reference kept):", skipped)
subprocess.run([sys.executable, str(S / "install_relift.py"), str(dest)], check=True)
