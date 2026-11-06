"""Write case.json for the msgpack-c msgpack_object_print_buffer case from the files beside this script.

  python3 make_case.py

original.c is src/objectc.c at the pinned revision, fixed.c the same file with the proposed
change, prelude.inc the type definitions from include/msgpack/object.h and stand-ins for
snprintf and isprint that only the model uses, harness.inc the harness body. The harness prints a BIN or
an EXT object of zero to two bytes into every buffer size from 0 to 24 and compares the
result with the text that msgpack_object_print() writes for the same object.
cross_check.py compares the stand-ins and the whole input domain with the C library.
"""
import hashlib
import json
import pathlib

root = pathlib.Path(__file__).resolve().parent
REVISION = "319ae6edf016327738b707cdb0d222b6091ae9f2"


def source(name, revision):
    lines = (root / name).read_text().split("\n")
    first = lambda start: next(i for i, line in enumerate(lines, 1) if line.startswith(start))
    end = lambda begin: next(i for i, line in enumerate(lines, 1) if i > begin and line == "}")
    macro = first("#define MSGPACK_CHECKED_CALL(")
    macro_end = next(i for i, line in enumerate(lines, 1) if i >= macro and not line.endswith("\\"))
    escape, show = first("static int msgpack_object_bin_print_buffer("), first("int msgpack_object_print_buffer(")
    return {"file": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(), "revision": revision,
            "definitions": [
                {"name": "MSGPACK_CHECKED_CALL", "kind": "macro", "line": macro, "end_line": macro_end,
                 "starts_with": lines[macro - 1]},
                {"name": "msgpack_object_bin_print_buffer", "line": escape, "end_line": end(escape),
                 "starts_with": lines[escape - 1]},
                {"name": "msgpack_object_print_buffer", "line": show, "end_line": end(show),
                 "starts_with": lines[show - 1]}]}


case = {
    "format": "dawnr-native-case-v1",
    "id": "msgpack-c-print-buffer-empty-bin",
    "repository": "msgpack/msgpack-c",
    "path": "src/objectc.c",
    "machine": "LP64",
    "sources": {"original": source("original.c", REVISION),
                "fixed": source("fixed.c", REVISION + " with the proposed change")},
    "prelude": (root / "prelude.inc").read_text(),
    "inputs": [{"name": "kind", "type": "unsigned char"}, {"name": "tag", "type": "signed char"},
               {"name": "count", "type": "unsigned char"}, {"name": "b0", "type": "unsigned char"},
               {"name": "b1", "type": "unsigned char"}, {"name": "room", "type": "unsigned char"}],
    "harness": (root / "harness.inc").read_text(),
    "assertions": ["print.result", "print.text", "print.nothing_after_the_given_size", "print.terminated"],
    "assumptions": 3,
    "loops": 2,
    "unwind": 10,
    "input_domain": ("a BIN object or an EXT object of every type from -128 to 127, with zero, one or two bytes of "
                     "every value, printed into every buffer size from 0 to 24"),
    "limitations": ("msgpack_object_print_buffer for BIN and EXT objects of at most two bytes, with "
                    "msgpack_object_bin_print_buffer and MSGPACK_CHECKED_CALL; the other object types, and with them "
                    "arrays and maps, are not examined; the model reads snprintf and isprint as the stand-ins in the "
                    "prelude: snprintf with ordinary characters and one %i, %d or %02x directive, isprint as in the C "
                    "locale; the replay of a counterexample calls the C library; the type definitions are not extracted by the gate "
                    "but copied into the prelude from include/msgpack/object.h at the same revision; an unwinding "
                    "bound of 10"),
}
(root / "case.json").write_text(json.dumps(case, indent=2) + "\n")
print(json.dumps(case["sources"], indent=1))
