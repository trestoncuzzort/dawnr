#!/usr/bin/env python3
"""F3, F4 and F5: every file named so far, each with its build's generated headers, with no harness written by hand. Nothing here is reported anywhere."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[2])
import native_scaffold as scaffold

SRC = Path("ROOT/src")
BUILD = Path("ROOT/build")
OUT = Path(sys.argv[1])
UV = [SRC / "libuv/include", SRC / "libuv/src"]
MSGPACK = [BUILD / "msgpack-c-ci-p4-pristine/build/include", BUILD / "msgpack-c-ci-p4-pristine/build/include/msgpack", SRC / "msgpack-c-pristine/include", SRC / "msgpack-c-pristine/include/msgpack"]
COAP = [BUILD / "libcoap-pristine", BUILD / "libcoap-pristine/include", SRC / "libcoap-pristine/include", SRC / "libcoap-pristine"]
LVGL = [SRC / "lvgl-memcmp"]
FLAC = [BUILD / "flac-pristine", SRC / "flac-pristine/include", SRC / "flac-pristine/src/libFLAC/include", SRC / "flac-pristine/src/share"]
EVENT = [BUILD / "libevent-pristine/include", SRC / "libevent-pristine/include", SRC / "libevent-pristine", SRC / "libevent-pristine/compat"]
FILES = [
    ("libuv", "libuv", "src/idna.c", UV, []),
    ("libuv", "libuv", "src/strscpy.c", UV, []),
    ("libuv", "libuv", "src/inet.c", UV, []),
    ("libuv", "libuv", "src/strtok.c", UV, []),
    ("msgpack-c", "msgpack-c-pristine", "src/version.c", MSGPACK, []),
    ("msgpack-c", "msgpack-c-pristine", "src/objectc.c", MSGPACK, []),
    ("msgpack-c", "msgpack-c-pristine", "src/zone.c", MSGPACK, []),
    ("libcoap", "libcoap-pristine", "src/coap_option.c", COAP, []),
    ("libcoap", "libcoap-pristine", "src/coap_encode.c", COAP, []),
    ("libcoap", "libcoap-pristine", "src/coap_str.c", COAP, []),
    ("lvgl", "lvgl-memcmp", "src/misc/lv_math.c", LVGL, ["LV_CONF_SKIP"]),
    ("lvgl", "lvgl-memcmp", "src/misc/lv_area.c", LVGL, ["LV_CONF_SKIP"]),
    ("flac", "flac-pristine", "src/libFLAC/crc.c", FLAC, ["HAVE_CONFIG_H"]),
    ("flac", "flac-pristine", "src/libFLAC/bitmath.c", FLAC, ["HAVE_CONFIG_H"]),
    ("flac", "flac-pristine", "src/share/utf8/charset.c", FLAC + [SRC / "flac-pristine/src/share/utf8"], ["HAVE_CONFIG_H"]),
    ("flac", "flac-pristine", "src/share/replaygain_analysis/replaygain_analysis.c", FLAC, ["HAVE_CONFIG_H"]),
    ("libevent", "libevent-pristine", "evutil_time.c", EVENT, []),
    ("libevent", "libevent-pristine", "strlcpy.c", EVENT, []),
    ("libevent", "libevent-pristine", "event_tagging.c", EVENT, []),
]
OUT.mkdir(parents=True, exist_ok=False)
summary = []
for project, tree, path, includes, defines in FILES:
    source = SRC / tree / path
    out = OUT / (project + "-" + path.replace("/", "_"))
    args = argparse.Namespace(include=[str(item) for item in includes] + [str(source.parent)], define=defines, compiler="gcc", machine="LP64", out=out, max_length=4, unwind=6, repository=project, revision=tree,
                              cbmc="ROOT/tools/bin/cbmc", timeout=60, memory_limit_mb=2048, solver="cadical", jobs=6, sample=20000)
    try:
        if not source.exists():
            raise ValueError("no such file in this tree")
        report = scaffold.scan(source, args)
    except Exception as error:
        row = {"project": project, "file": path, "error": str(error)[:400]}
        summary.append(row)
        print(json.dumps(row), flush=True)
        continue
    refusals = {}
    for item in report["refused"]:
        reason = item["refused"].split(" (")[0]
        refusals[reason] = refusals.get(reason, 0) + 1
    row = {"project": project, "file": path, "functions": report["functions"], "drafted": report["drafted"], "refused": len(report["refused"]), "refusals": refusals, "verdicts": report["verdicts"],
           "candidates": [item["function"] for item in report["candidates"]]}
    summary.append(row)
    print(json.dumps(row), flush=True)
(OUT / "wide.json").write_text(json.dumps(summary, indent=1) + "\n")
totals = {"functions": sum(row.get("functions", 0) for row in summary), "drafted": sum(row.get("drafted", 0) for row in summary), "candidates": sum(len(row.get("candidates", [])) for row in summary)}
verdicts, refusals = {}, {}
for row in summary:
    for key, value in row.get("verdicts", {}).items():
        verdicts[key] = verdicts.get(key, 0) + value
    for key, value in row.get("refusals", {}).items():
        refusals[key] = refusals.get(key, 0) + value
print(json.dumps({"totals": totals, "verdicts": verdicts, "refusals": refusals, "failed_files": [row["file"] for row in summary if "error" in row]}))
