"""Write case.json for the inav uvarintEncode case from the files beside this script.

  python3 make_case.py

original.c is src/main/common/uvarint.c at the pinned revision, fixed.c the same file with
the proposed change, harness.inc the harness body. The harness compares uvarintEncode with
the uvarint_t rules of the FrSky OSD protocol text
(https://github.com/hydra/FrSkyPixelOSD/blob/master/doc/OSD.md) for every 32-bit value and
every buffer size from 0 to 5, and reads each result back with uvarintDecode.
"""
import hashlib
import json
import pathlib

root = pathlib.Path(__file__).resolve().parent
REVISION = "b006087bf26a12f3f7df478af4c6170d16b22755"


def source(name, revision):
    lines = (root / name).read_text().split("\n")
    first = lambda start: next(i for i, line in enumerate(lines, 1) if line.startswith(start))
    end = lambda begin: next(i for i, line in enumerate(lines, 1) if i > begin and line == "}")
    encode, decode = first("int uvarintEncode("), first("int uvarintDecode(")
    return {"file": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(), "revision": revision,
            "definitions": [
                {"name": "uvarintEncode", "line": encode, "end_line": end(encode), "starts_with": lines[encode - 1]},
                {"name": "uvarintDecode", "line": decode, "end_line": end(decode), "starts_with": lines[decode - 1]}]}


case = {
    "format": "dawnr-native-case-v1",
    "id": "inav-uvarint-encode",
    "repository": "iNavFlight/inav",
    "path": "src/main/common/uvarint.c",
    "machine": "ILP32",
    "sources": {"original": source("original.c", REVISION),
                "fixed": source("fixed.c", REVISION + " with the proposed change")},
    # The compiler's own type macros: the 32-bit model then needs no 32-bit C library headers.
    "prelude": ("typedef __UINT8_TYPE__ uint8_t;\ntypedef __UINT32_TYPE__ uint32_t;\n"
                "typedef __SIZE_TYPE__ size_t;\n"),
    "inputs": [{"name": "val", "type": "uint32_t"}, {"name": "size", "type": "unsigned char"}],
    "harness": (root / "harness.inc").read_text(),
    "assertions": ["uvarint.length", "uvarint.bytes", "uvarint.decoder_reads_it_back", "uvarint.no_write_without_room"],
    "assumptions": 1,
    "loops": 2,
    "unwind": 6,
    "input_domain": "every 32-bit value with every buffer size from 0 to 5 bytes",
    "limitations": ("uvarintEncode, and uvarintDecode only on the bytes that a correct encoder writes; the overflow "
                    "check of uvarintDecode and the callers in the FrSky OSD driver are not examined; when the value "
                    "does not fit, only the return value is required"),
}
(root / "case.json").write_text(json.dumps(case, indent=2) + "\n")
print(json.dumps(case["sources"], indent=1))
