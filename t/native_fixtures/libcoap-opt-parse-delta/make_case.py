"""Write case.json for the libcoap coap_opt_parse delta case from the files beside this script.

  python3 make_case.py

original.c is src/coap_option.c at the pinned revision, fixed.c the same file with the proposed
change, prelude.inc the type definitions and the payload marker from include/coap3/coap_option.h
and include/coap3/coap_pdu_internal.h, a stand-in for the debug log macro and the static
buffer, harness.inc the harness body.

The harness parses an option header of five input bytes in a buffer of every length from 0 to
65809 and compares the result with the option format of RFC 7252 section 3.1
(https://www.rfc-editor.org/rfc/rfc7252#section-3.1): the nibbles of the first byte, the extra
bytes (nibble 13: one byte plus 13, nibble 14: two bytes in network order plus 269, nibble 15
reserved) and the option number as the sum of the deltas. Option numbers are 16 bits wide
(RFC 7252 section 12.2, https://www.rfc-editor.org/rfc/rfc7252#section-12.2), so a delta above
65535 is invalid. The harness computes delta, length and header size from the input bytes with
32-bit arithmetic, without reading the function.
"""
import hashlib
import json
import pathlib

root = pathlib.Path(__file__).resolve().parent
REVISION = "45ace062bf5cbe60ef9e4e4883fc844228c5f8ca"


def source(name, revision):
    lines = (root / name).read_text().split("\n")
    first = lambda start: next(i for i, line in enumerate(lines, 1) if line.startswith(start))
    end = lambda begin: next(i for i, line in enumerate(lines, 1) if i > begin and line == "}")
    advance = first("#define ADVANCE_OPT(")
    advance_end = next(i for i, line in enumerate(lines, 1) if i >= advance and not line.endswith("\\"))
    check = first("#define ADVANCE_OPT_CHECK(")
    check_end = next(i for i, line in enumerate(lines, 1) if i >= check and not line.endswith("\\"))
    parse = next(i for i, line in enumerate(lines, 1) if line == "size_t" and lines[i].startswith("coap_opt_parse("))
    return {"file": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(), "revision": revision,
            "definitions": [
                {"name": "ADVANCE_OPT", "kind": "macro", "line": advance, "end_line": advance_end,
                 "starts_with": lines[advance - 1]},
                {"name": "ADVANCE_OPT_CHECK", "kind": "macro", "line": check, "end_line": check_end,
                 "starts_with": lines[check - 1]},
                {"name": "coap_opt_parse", "line": parse, "end_line": end(parse), "starts_with": "size_t"}]}


case = {
    "format": "dawnr-native-case-v1",
    "id": "libcoap-opt-parse-delta",
    "repository": "obgm/libcoap",
    "path": "src/coap_option.c",
    "machine": "LP64",
    "sources": {"original": source("original.c", REVISION),
                "fixed": source("fixed.c", REVISION + " with the proposed change")},
    "prelude": (root / "prelude.inc").read_text(),
    "inputs": [{"name": "h0", "type": "unsigned char"}, {"name": "h1", "type": "unsigned char"},
               {"name": "h2", "type": "unsigned char"}, {"name": "h3", "type": "unsigned char"},
               {"name": "h4", "type": "unsigned char"}, {"name": "room", "type": "unsigned int"}],
    "harness": (root / "harness.inc").read_text(),
    "assertions": ["opt.zero_exactly_when_invalid", "opt.delta", "opt.length", "opt.value", "opt.size",
                   "opt.nothing_else_written"],
    "assumptions": 1,
    "loops": 0,
    "input_domain": ("the first five bytes of the option buffer (the header byte, then up to two extra delta bytes "
                     "and two extra length bytes) with every value, and a buffer length from 0 to 65809 (the longest "
                     "header of 5 bytes plus the longest value of 65804 bytes); bytes of the buffer after the fifth "
                     "are zero and are not read by the function"),
    "limitations": ("coap_opt_parse with ADVANCE_OPT and ADVANCE_OPT_CHECK; the callers (option iterators, PDU "
                    "parsing) are not examined; the type definitions, COAP_PAYLOAD_START and a buffer are not "
                    "extracted by the gate but copied or written into the prelude from include/coap3/coap_option.h "
                    "and include/coap3/coap_pdu_internal.h at the same revision; coap_log_debug is a macro that does "
                    "nothing, so the log messages are not examined; the function does not read option value bytes, "
                    "so the value bytes are not modelled; the contents of the result structure are checked only "
                    "when the function returns a size other than 0; the check that nothing else is written looks at "
                    "four guard bytes on each side of the result structure and does not look at its padding"),
}
(root / "case.json").write_text(json.dumps(case, indent=2) + "\n")
print(json.dumps(case["sources"], indent=1))
