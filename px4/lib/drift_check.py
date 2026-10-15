#!/usr/bin/env python3
"""Source-faithfulness check for a PX4 formal gate.

A gate's model.t is a hand-written faithful abstraction of a specific PX4 function; the proof is only as
meaningful as that faithfulness. Each gate records `source.json`:
  {"file": "src/modules/rc_update/rc_update.cpp", "symbol": "RCUpdate::getChannelIndex", "sha256": "..."}
This re-extracts that function's text from the PX4 tree (brace-matched from the symbol's definition line) and
compares its sha256. Match => the modeled code is unchanged. Drift => the PX4 function changed since the model
was reviewed; re-review model.t and re-record the hash. This does NOT prove the model matches the code (that
is a human review); it makes silent drift impossible to miss.

    python3 drift_check.py <gate-dir> <px4-root> [--update]
"""
import argparse
import hashlib
import json
import pathlib
import re


def extract_function(src_text, symbol):
    """Return the text of the first C/C++ definition of `symbol` (from its signature line through the
    brace-matched closing brace), or None. `symbol` may be `Class::method` or a bare function name."""
    # find a definition line: the symbol followed (after an argument list) by an opening brace on some line
    esc = re.escape(symbol)
    lines = src_text.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if re.search(rf"(^|[^\w:]){esc}\s*\(", ln) and not ln.lstrip().startswith(("//", "*")):
            # walk forward to the first '{' that opens the body, then brace-match
            buf = "".join(lines[i:])
            b = buf.find("{")
            if b < 0:
                continue
            # reject pure declarations (';' before any '{')
            semi = buf.find(";")
            if 0 <= semi < b:
                continue
            depth, j = 0, b
            while j < len(buf):
                c = buf[j]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return buf[:j + 1]
                j += 1
    return None


def check(gate_dir, px4_root, update=False):
    g = pathlib.Path(gate_dir)
    meta = json.loads((g / "source.json").read_text())
    f = pathlib.Path(px4_root) / meta["file"]
    if not f.is_file():
        return "MISSING", f"{meta['file']} not found under {px4_root}"
    fn = extract_function(f.read_text(errors="replace"), meta["symbol"])
    if fn is None:
        return "MISSING", f"symbol {meta['symbol']} not found in {meta['file']}"
    h = hashlib.sha256(fn.encode()).hexdigest()
    if update:
        meta["sha256"] = h
        (g / "source.json").write_text(json.dumps(meta, indent=1))
        return "UPDATED", h[:16]
    if meta.get("sha256") == h:
        return "OK", h[:16]
    return "DRIFT", f"recorded {str(meta.get('sha256'))[:16]} != current {h[:16]} -- re-review {g.name}/model.t"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gate_dir")
    ap.add_argument("px4_root")
    ap.add_argument("--update", action="store_true", help="record the current function hash (first-time or after re-review)")
    a = ap.parse_args()
    status, detail = check(a.gate_dir, a.px4_root, a.update)
    print(f"{status}: {detail}")
    return 0 if status in ("OK", "UPDATED") else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
