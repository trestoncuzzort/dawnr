"""Write case.json for the xiph/flac metaflac parse_uint32 case from the files beside this script.

  python3 make_case.py

original.c is src/metaflac/options.c at the pinned revision, fixed.c the same file with the
proposed change, prelude.inc the integer types, the licence notice and the prototypes copied from
the project plus stand-ins for strlen, strspn, strtoul and strtoull that only the model uses, harness.inc
the harness body.

The harness takes a string of 0 to 11 characters (the bytes b0 to b10 up to the first NUL byte),
each character any byte, and calls parse_uint32 and, for a string of decimal digits,
parse_add_padding. The reference is the decimal value of the digits, computed in the harness with
64-bit arithmetic (C11 7.22.1.4, https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf), and
the use of the value by the callers in the same file; for parse_add_padding it is the 24 bit
length field of a metadata block header (https://xiph.org/flac/format.html#metadata_block_header)
and man/metaflac.md. cross_check.py compares the stand-ins with the C library and runs the
harness natively over a stated sample of the input domain for both variants.
"""
import hashlib
import json
import pathlib

root = pathlib.Path(__file__).resolve().parent
REVISION = "59fa3402cb19b6b7c85b916f138cfb03c7b27504"
FUNCTIONS = ("parse_uint32", "parse_uint64", "parse_add_padding")


def source(name, revision):
    lines = (root / name).read_text().split("\n")
    definitions = []
    for function in FUNCTIONS:
        begin = next(i for i, line in enumerate(lines, 1) if line.startswith(f"FLAC__bool {function}("))
        end = next(i for i, line in enumerate(lines, 1) if i > begin and line == "}")
        definitions.append({"name": function, "line": begin, "end_line": end, "starts_with": lines[begin - 1]})
    return {"file": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(), "revision": revision,
            "definitions": definitions}


case = {
    "format": "dawnr-native-case-v1",
    "id": "flac-metaflac-parse-uint32",
    "repository": "xiph/flac",
    "path": "src/metaflac/options.c",
    "machine": "LP64",
    "sources": {"original": source("original.c", REVISION),
                "fixed": source("fixed.c", REVISION + " with the proposed change")},
    "prelude": (root / "prelude.inc").read_text(),
    "inputs": [{"name": f"b{i}", "type": "unsigned char"} for i in range(11)],
    "harness": (root / "harness.inc").read_text(),
    "assertions": ["uint32.result", "uint32.value", "uint32.untouched_on_refusal", "padding.result", "padding.value"],
    "assumptions": 0,
    "loops": 0,
    "unwind": 12,
    "input_domain": ("a string of 0 to 11 characters, each character any byte except NUL, given as the bytes b0 to b10 up to "
                     "the first NUL byte; parse_add_padding is called when the string is one or more decimal digits"),
    "limitations": ("parse_uint32, parse_uint64 and parse_add_padding; parse_block_number, which the proposed change "
                    "also edits to call parse_uint32, uses strdup, free and strchr and is not examined; strings of up to "
                    "11 characters, so 11 digits reach 99999999999 and no string reaches the 64-bit limit; "
                    "parse_add_padding only for strings of decimal digits, not for white space, signs or text, "
                    "which strtoul accepts or reads as 0; the model reads strlen, strspn, strtoul and strtoull as the "
                    "stand-ins in the prelude: base 10, the accept set 0123456789 and a string without white space or "
                    "sign at its start, anything else fails a property of the stand-in; the replay of a "
                    "counterexample calls the C library; the integer types, the notice, the assert macro, the constant "
                    "FLAC__STREAM_METADATA_LENGTH_LEN and the prototypes are not extracted by the gate but copied "
                    "into the prelude from include/FLAC/ordinals.h, include/FLAC/assert.h, src/libFLAC/format.c and "
                    "src/metaflac/options.c at the same revision; FLAC__ASSERT is the C library assert; parse_uint64 "
                    "is listed for both variants but only the fixed parse_uint32 calls it; the unwinding bound is 12"),
}
(root / "case.json").write_text(json.dumps(case, indent=2) + "\n")
print(json.dumps(case["sources"], indent=1))
