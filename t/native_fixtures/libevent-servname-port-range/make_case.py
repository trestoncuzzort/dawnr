"""Write case.json for the libevent parse_numeric_servname case from the files beside this script.

  python3 make_case.py

original.c is evutil.c at the pinned revision, fixed.c the same file with the proposed change
(the value of strtol is kept in a long for the range check). prelude.inc holds a stand-in for
strtol that only the model uses, harness.inc the harness body. The harness calls
parse_numeric_servname on every string of 0 to 11 characters of any value but the terminator and
compares the result with the port number that the text denotes.

The reference is not the code under check. A port number is 0 to 65535: RFC 6335 section 6,
https://www.rfc-editor.org/rfc/rfc6335#section-6. The value of the text is computed in the harness
in 64 bits from its characters, with the reading of C11 7.22.1.4 for strtol in base 10 (white space,
an optional sign, decimal digits): https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf.

cross_check.py compares the stand-in with the C library and runs the harness natively over a
large part of the input domain for both variants.
"""
import hashlib
import json
import pathlib

root = pathlib.Path(__file__).resolve().parent
REVISION = "d82464a277d0f42703702c4dfd9af6af38595a83"


def source(name, revision):
    lines = (root / name).read_text().split("\n")
    name_line = next(i for i, line in enumerate(lines, 1) if line.startswith("parse_numeric_servname(const char *servname)"))
    first = name_line - 1
    end = next(i for i, line in enumerate(lines, 1) if i > first and line == "}")
    return {"file": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(), "revision": revision,
            "definitions": [
                {"name": "parse_numeric_servname", "line": first, "end_line": end,
                 "starts_with": lines[first - 1]}]}


case = {
    "format": "dawnr-native-case-v1",
    "id": "libevent-servname-port-range",
    "repository": "libevent/libevent",
    "path": "evutil.c",
    "machine": "LP64",
    "sources": {"original": source("original.c", REVISION),
                "fixed": source("fixed.c", REVISION + " with the proposed change")},
    "prelude": (root / "prelude.inc").read_text(),
    "inputs": [{"name": "count", "type": "unsigned char"}] + [{"name": f"ch{i}", "type": "unsigned char"} for i in range(11)],
    "harness": (root / "harness.inc").read_text(),
    "assertions": ["servname.range", "servname.digits", "servname.value", "servname.empty", "servname.trailing",
                   "servname.no_digits"],
    "assumptions": 12,
    "loops": 2,
    "unwind": 12,
    "input_domain": ("every string of 0 to 11 characters, each of any value except 0, followed by the terminator; "
                     "the characters after the terminator are of any value"),
    "limitations": ("parse_numeric_servname alone, for strings of at most 11 characters; callers, locale and errno "
                    "are not examined; the model reads strtol as the stand-in in the prelude, which is exact for "
                    "base 10 only and does not set errno, and the replay of a counterexample calls the C library; "
                    "the expected value is computed for white space, a sign and decimal digits as C11 7.22.1.4 "
                    "reads them, and the case does not say that the function should accept white space or a sign; "
                    "a bound of 12 on every loop"),
}
(root / "case.json").write_text(json.dumps(case, indent=2) + "\n")
print(json.dumps(case["sources"], indent=1))
