"""Write case.json for the open62541 UA_DateTime_parse case from the files beside this script.

  python3 make_case.py

original.c is src/ua_types.c at the pinned revision and fixed.c the same file with the
proposed change. prelude.inc holds the types, macros and helper functions that the parser
uses, taken from the same revision; each block names its file and lines. harness.inc is the
harness body. The harness builds the string [+-]YYYY[Y]-01-01T00:00:00Z from its inputs and
compares UA_DateTime_parse with a day count of the proleptic Gregorian calendar
(https://howardhinnant.github.io/date_algorithms.html#days_from_civil).
"""
import hashlib
import json
import pathlib

root = pathlib.Path(__file__).resolve().parent
REVISION = "24fc6b296c53c42bc70349b7ded63c18339ff22f"


def source(name, revision):
    lines = (root / name).read_text().split("\n")
    named = next(i for i, line in enumerate(lines, 1) if line.startswith("UA_DateTime_parse(UA_DateTime *dst, const UA_String str) {"))
    first = named - 1  # the return type stands on its own line
    last = next(i for i, line in enumerate(lines, 1) if i > first and line == "}")
    return {"file": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(), "revision": revision,
            "definitions": [{"name": "UA_DateTime_parse", "line": first, "end_line": last, "starts_with": lines[first - 1]}]}


case = {
    "format": "dawnr-native-case-v1",
    "id": "open62541-datetime-parse-year",
    "repository": "open62541/open62541",
    "path": "src/ua_types.c",
    "machine": "LP64",
    "sources": {"original": source("original.c", REVISION),
                "fixed": source("fixed.c", REVISION + " with the proposed change")},
    "prelude": (root / "prelude.inc").read_text(),
    "inputs": [{"name": f"d{i}", "type": "unsigned char"} for i in range(5)]
              + [{"name": "sign", "type": "unsigned char"}, {"name": "digits", "type": "unsigned char"}],
    "harness": (root / "harness.inc").read_text(),
    "assertions": ["datetime.accepted_iff_representable", "datetime.value"],
    "assumptions": 1,
    "loops": 3,
    "unwind": 6,
    "input_domain": ("every string [+-]YYYY[Y]-01-01T00:00:00Z: four or five year digits with no sign, "
                     "a plus sign or a minus sign"),
    "limitations": ("UA_DateTime_parse only; month, day, time and zone are fixed to -01-01T00:00:00Z and there is no "
                    "fraction; parseInt64 and parseUInt64 (deps/parse_num.c), musl_tm_to_secs and its helpers "
                    "(deps/libc_time.c), isTrue and UA_CHECK (src/util/ua_util_internal.h) and the type and constant "
                    "definitions are not extracted by the gate but copied into the prelude from the same revision; "
                    "three loops, two in parseUInt64 and the fraction loop of UA_DateTime_parse, with an unwinding "
                    "bound of 6"),
}
(root / "case.json").write_text(json.dumps(case, indent=2) + "\n")
print(json.dumps(case["sources"], indent=1))
