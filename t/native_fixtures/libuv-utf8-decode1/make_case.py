"""Write case.json for the libuv UTF-8 decoder case from the files beside this script.

  python3 make_case.py

original.c is src/idna.c at the pinned revision, fixed.c the same file with the proposed
change, harness.inc the harness body. The harness compares uv__utf8_decode1 with the table
of well-formed UTF-8 byte sequences (RFC 3629 section 4, Unicode table 3-7) on every input
of 1 to 5 bytes.
"""
import hashlib
import json
import pathlib

root = pathlib.Path(__file__).resolve().parent
REVISION = "9e40720a0cdfd99970eacc43b39fa1404c6df38d"


def source(name, revision):
    lines = (root / name).read_text().split("\n")
    slow = next(i for i, line in enumerate(lines, 1) if line.startswith("static unsigned uv__utf8_decode1_slow("))
    fast = next(i for i, line in enumerate(lines, 1) if line.startswith("unsigned uv__utf8_decode1("))
    end = lambda first: next(i for i, line in enumerate(lines, 1) if i > first and line == "}")
    return {"file": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(), "revision": revision,
            "definitions": [
                {"name": "uv__utf8_decode1_slow", "line": slow, "end_line": end(slow), "starts_with": lines[slow - 1]},
                {"name": "uv__utf8_decode1", "line": fast, "end_line": end(fast), "starts_with": lines[fast - 1]}]}


case = {
    "format": "dawnr-native-case-v1",
    "id": "libuv-utf8-decode1",
    "repository": "libuv/libuv",
    "path": "src/idna.c",
    "machine": "LP64",
    "sources": {"original": source("original.c", REVISION),
                "fixed": source("fixed.c", REVISION + " with the proposed change")},
    "prelude": "#include <assert.h>\n",
    "inputs": [{"name": f"b{i}", "type": "unsigned char"} for i in range(5)] + [{"name": "len", "type": "unsigned int"}],
    "harness": (root / "harness.inc").read_text(),
    "assertions": ["utf8.wellformed_decoded", "utf8.illformed_rejected", "utf8.cursor_in_bounds"],
    "assumptions": 1,
    "loops": 0,
    "input_domain": "every input of 1 to 5 bytes, decoded from its first byte",
    "limitations": ("uv__utf8_decode1 and uv__utf8_decode1_slow only; 0 to 4 bytes follow the first byte, and the "
                    "function distinguishes 0, 1, 2 and 3 or more; after an ill-formed sequence the cursor is only "
                    "required to lie inside the input"),
}
(root / "case.json").write_text(json.dumps(case, indent=2) + "\n")
print(json.dumps(case["sources"], indent=1))
