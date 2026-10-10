#!/usr/bin/env python3
"""t/flight/px4_stmt.py: PX4's own statements, before and after each proposed fix, against the t findings and fixes.

The MAVLink and commander defects live inside handlers that need a running module (a Mavlink instance, the commander),
so px4_diff.py cannot call them. This harness compiles the statements themselves instead. It fetches the handler's
source file twice: at the pinned commit (the code the finding restates) and at the fix branch's commit on the fork the
pull request comes from (the code the fix restates). It cuts out the lines between two markers, verbatim, and
compiles them inside a small function. Only the surrounding names are stand-ins: the message struct with MAVLink's
field types, the enum values, and for SERIAL_CONTROL the serial passthrough (named below). The program runs each
input and prints what PX4's lines leave behind. t's interpreter runs the finding and the fix at the same input, and
the two are compared.

Inputs reach the program on stdin, so the compiler cannot fold an out-of-range conversion at build time. Results
are x86-64 (GCC); the README says where ARM differs.

  python3 t/flight/px4_stmt.py [--table PX4-STMT.md]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import interp  # noqa: E402
import tasks_io  # noqa: E402
import evidence  # noqa: E402
from px4_diff import PX4_COMMIT, _run_cpp_process, fetch_px4  # noqa: E402

FORK = "trestoncuzzort/PX4-Autopilot"
CACHE = HERE.parent / "out" / "px4-stmt"
CXX_FLAGS = ["-std=c++17", "-O1", "-w"]
PRELUDE = ("#include <cmath>\n#include <cstdint>\n#include <cstdio>\n#include <cstring>\n#include <vector>\n"
           "#include <mathlib/mathlib.h>\n")

# name -> the source file; (start, end) markers for the original and for the fix (end None: the start line only;
# "}": up to the first line, after start, that is only a closing brace at the start line's indent or less); the fix
# branch's commit; the C++ around the lines; how a t input is fed in; the finding and fix tasks.
PAIRS = {
    "arm_disarm": {
        "file": "src/modules/commander/Commander.cpp", "pr": 29036,
        "fix_commit": "96d9bbbb1e9a831021bf2013ff8134a5efcf0e08",
        "orig": ("const int8_t arming_action = static_cast<int8_t>(lroundf(cmd.param1));", None),
        "fixed": ("const float arming_param = roundf(cmd.param1);", "const int8_t arming_action ="),
        # vehicle_command_s::ARMING_ACTION_DISARM = 0, ARMING_ACTION_ARM = 1 (msg/versioned/VehicleCommand.msg)
        "wrap": ("struct cmd_s { float param1; };\n"
                 "static long long run(long long p) { const cmd_s cmd{(float)p};\n{LINES}\n"
                 "  return arming_action == 1 ? 1 : (arming_action == 0 ? 0 : -1); }\n"),
        "finding": "findings/px4_arm_param_any.t", "fix": "fixes/px4_arm_param_fixed.t", "param": "p",
    },
    "set_mode": {
        "file": "src/modules/commander/Commander.cpp", "pr": 29036,
        "fix_commit": "96d9bbbb1e9a831021bf2013ff8134a5efcf0e08",
        "orig": ("uint8_t base_mode = (uint8_t)cmd.param1;", None),
        "fixed": ("static bool mode_field_to_uint8(float value, uint8_t &out)", "}"),
        # DO_SET_MODE's base mode field; the fix's helper is a file-scope function, called as the handler calls it
        "wrap": ("struct cmd_s { float param1; };\n"
                 "static long long run(long long p) { const cmd_s cmd{(float)p};\n{LINES}\n  return base_mode; }\n"),
        "wrap_fixed": ("{LINES}\nstruct cmd_s { float param1; };\n"
                       "static long long run(long long p) { const cmd_s cmd{(float)p}; uint8_t base_mode = 0;\n"
                       "  bool mode_fields_valid = mode_field_to_uint8(cmd.param1, base_mode);\n"
                       "  return mode_fields_valid ? base_mode : -1; }\n"),
        "finding": "findings/px4_set_mode_field_any.t", "fix": "fixes/px4_set_mode_field_fixed.t", "param": "p",
    },
    "request_event": {
        "file": "src/modules/mavlink/mavlink_events.cpp", "pr": 29033,
        "fix_commit": "0e222f30c7f3c74c92d57d94c810f9a06c202235",
        "orig": ("const uint16_t end_sequence = request_event.last_sequence + 1;", "}"),
        "fixed": ("const uint16_t end_sequence = request_event.last_sequence + 1;", "}#2"),
        # an event buffer of the given capacity holding no event (every lookup misses, as for a sequence long gone);
        # the result is the number of lookups, t's `lookups`
        "wrap": ("#define PX4_DEBUG(...)\n"
                 "enum { MAV_EVENT_ERROR_REASON_UNAVAILABLE = 0 };\n"
                 "struct Event {};\n"
                 "struct mavlink_request_event_t { uint16_t first_sequence; uint16_t last_sequence; };\n"
                 "struct mavlink_message_t { uint8_t sysid; uint8_t compid; };\n"
                 "struct mavlink_response_event_error_t { uint8_t target_system; uint8_t target_component;"
                 " uint16_t sequence; uint16_t sequence_oldest_available; uint8_t reason; };\n"
                 "static long long lookups = 0;\n"
                 "struct EventBuffer { int cap; bool get_event(uint16_t, Event &) const { lookups++; return false; }\n"
                 "  uint16_t get_oldest_sequence_after(uint16_t s) const { return s; } int capacity() const { return cap; } };\n"
                 "struct Chan { int get_channel() const { return 0; } };\n"
                 "static void mavlink_msg_response_event_error_send_struct(int, const mavlink_response_event_error_t *) {}\n"
                 "static void send_event(const Event &) {}\n"
                 "static long long run(long long first, long long last, long long capacity) {\n"
                 "  const EventBuffer _buffer{(int)capacity}; const Chan _mavlink{}; const mavlink_message_t msg{1, 1};\n"
                 "  mavlink_request_event_t request_event{(uint16_t)first, (uint16_t)last}; Event e; lookups = 0;\n"
                 "{LINES}\n  return lookups; }\n"),
        "finding": "findings/px4_request_event_any.t", "fix": "fixes/px4_request_event_fixed.t",
        "params": ["first", "last", "capacity"], "keep": lambda v: v["capacity"] <= 65535,
    },
    "fusion_source": {
        "file": "src/modules/ekf2/EKF2.cpp", "pr": 29039, "pinned": "df387bdec263fb4190eca5f061ce63091a6a758f",
        "fix_commit": "484d183bc95934fe669ca4b64e5ffb063c958719",
        "orig": ("const uint8_t sensor_type = static_cast<uint8_t>(cmd.param1);", "}"),
        "fixed": ("// The source, instance and enable flag are integers carried in floats.", "}#2"),
        # VEHICLE_CMD_ESTIMATOR_SENSOR_ENABLE with source p, instance unused (NaN) and enable 1; the result is the
        # source whose fusion flag the handler would set (FUSION_SOURCE_*), or -1 for none
        "wrap": ("struct FusionSensor { bool enabled; bool available; };\n"
                 "static constexpr int MAX_AGP_INSTANCES = 2;\n"
                 "struct FC { FusionSensor gps, of, ev, agp[MAX_AGP_INSTANCES], baro, rng, mag, aspd, rngbcn; };\n"
                 "static FC _fc;\n"
                 "struct vehicle_command_s { float param1, param2, param3;\n"
                 "  static constexpr uint8_t FUSION_SOURCE_GPS = 0, FUSION_SOURCE_OF = 1, FUSION_SOURCE_EV = 2,"
                 " FUSION_SOURCE_AGP = 3, FUSION_SOURCE_BARO = 4, FUSION_SOURCE_RNG = 5, FUSION_SOURCE_MAG = 6,"
                 " FUSION_SOURCE_ASPD = 7, FUSION_SOURCE_RNGBCN = 8; };\n"
                 "struct vehicle_command_ack_s { uint8_t result; static constexpr uint8_t VEHICLE_CMD_RESULT_DENIED = 2,"
                 " VEHICLE_CMD_RESULT_UNSUPPORTED = 3; };\n"
                 "static long long run(long long p) { const vehicle_command_s cmd{(float)p, NAN, 1.f};\n"
                 "  vehicle_command_ack_s ack{}; long long out = -1;\n"
                 "  [&]() {\n{LINES}\n"
                 "    const FusionSensor *all[] = {&_fc.gps, &_fc.of, &_fc.ev, &_fc.agp[0], &_fc.baro, &_fc.rng, &_fc.mag,"
                 " &_fc.aspd, &_fc.rngbcn};\n"
                 "    for (int k = 0; k < 9; k++) if (sensor == all[k]) out = k; }();\n"
                 "  return out; }\n"),
        "finding": "findings/px4_fusion_source_any.t", "fix": "fixes/px4_fusion_source_fixed.t", "param": "p",
    },
    "stream_interval": {
        "file": "src/modules/mavlink/mavlink_main.cpp", "pr": 29034,
        "fix_commit": "997da58b2d7b931ab89e5e0bf887c6303c1fac41",
        "orig": ("interval = (1000000.0f / rate);", None),
        "fixed": ("const float interval_us = 1000000.0f / rate;", "interval = (interval_us <"),
        # the t tasks take the interval the division denotes; the input is the rate that gives it, and the program
        # also prints the division's own value, which is the input t runs at
        "wrap": ("static long long run(long long x, long long *q) { const float rate = 1000000.0f / (float)x;\n"
                 "  int interval = 0;\n{LINES}\n"
                 "  *q = (long long)(1000000.0f / rate); return interval; }\n"),
        "finding": "findings/px4_stream_interval_any.t", "fix": "fixes/px4_stream_interval_fixed.t", "param": "x",
    },
    "do_jump": {
        "file": "src/modules/mavlink/mavlink_mission.cpp", "pr": 29035,
        "fix_commit": "1ef387249e11a2525f11e17a70e69280f09994dd",
        "orig": ("case MAV_CMD_DO_JUMP:", "break;"),
        "fixed": ("case MAV_CMD_DO_JUMP: {", "break;"),
        "wrap": ("enum { MAV_CMD_DO_JUMP = 177 }; enum { NAV_CMD_DO_JUMP = 177 };\n"
                 "enum { MAV_MISSION_ACCEPTED = 0, MAV_MISSION_INVALID_PARAM1 = 6 };\n"
                 "struct mavlink_mission_item_t { float param1; float param2; uint16_t command; };\n"
                 "struct mission_item_s { int nav_cmd; int16_t do_jump_mission_index; uint16_t do_jump_current_count;"
                 " uint16_t do_jump_repeat_count; };\n"
                 "static int parse(const mavlink_mission_item_t *mavlink_mission_item, mission_item_s *mission_item) {\n"
                 "  switch (mavlink_mission_item->command) {\n{LINES}\n  default: break; }\n"
                 "  return MAV_MISSION_ACCEPTED; }\n"
                 "static long long run(long long p) { mavlink_mission_item_t m{(float)p, 0.f, MAV_CMD_DO_JUMP};\n"
                 "  mission_item_s mi{}; return parse(&m, &mi) == MAV_MISSION_INVALID_PARAM1 ? -1 :"
                 " mi.do_jump_mission_index; }\n"),
        "finding": "findings/px4_do_jump_index_any.t", "fix": "fixes/px4_do_jump_index_fixed.t", "param": "p",
    },
    "serial_control": {
        "file": "src/modules/mavlink/mavlink_receiver.cpp", "pr": 29032,
        "fix_commit": "9106bf6b81cbaeb65da4e0488fb5c82650eaf38d",
        "orig": ("if (sp && serial_control_mavlink.count > 0", "}"),
        "fixed": ("if (sp && serial_control_mavlink.count > 0", "}"),
        # mavlink_serial_control_t's fields in MAVLink's own (packed) order. The stand-in for SerialPassthrough's
        # pushFromMavlink appends `len` bytes from `data`, as PX4's memcpy into its rx buffer does, and records
        # whether the bytes it was handed run past the message's 70-byte data field.
        "wrap": ("#pragma pack(push, 1)\n"
                 "struct mavlink_serial_control_t { uint32_t baudrate; uint16_t timeout; uint8_t device; uint8_t flags;"
                 " uint8_t count; uint8_t data[70]; uint8_t target_system; uint8_t target_component; };\n"
                 "#pragma pack(pop)\n"
                 "static mavlink_serial_control_t serial_control_mavlink;\n"
                 "struct mavlink_message_t { uint8_t sysid; uint8_t compid; };\n"
                 "struct Chan { int get_channel() { return 0; } } _mavlink;\n"
                 "static bool past_field = false;\n"
                 "struct SerialPassthrough { std::vector<int> rx;\n"
                 "  void pushFromMavlink(const uint8_t *data, size_t len, uint8_t, uint8_t, uint8_t, uint8_t) {\n"
                 "    if (data + len > serial_control_mavlink.data + sizeof(serial_control_mavlink.data))"
                 " past_field = true;\n"
                 "    for (size_t i = 0; i < len; i++) rx.push_back(data[i]); } };\n"
                 "static long long run(long long count) {\n"
                 "  for (int i = 0; i < 70; i++) serial_control_mavlink.data[i] = (uint8_t)(i % 251);\n"
                 "  serial_control_mavlink.count = (uint8_t)count; past_field = false;\n"
                 "  SerialPassthrough passthrough; SerialPassthrough *sp = &passthrough;\n"
                 "  mavlink_message_t message{1, 1}; mavlink_message_t *msg = &message;\n{LINES}\n"
                 "  for (size_t i = 0; i < passthrough.rx.size() && i < 70; i++)"
                 " if (passthrough.rx[i] != serial_control_mavlink.data[i]) return -2;\n"
                 "  return past_field ? -1 : (long long)passthrough.rx.size(); }\n"),
        "finding": "findings/px4_serial_control_any.t", "fix": "fixes/px4_serial_control_fixed.t", "param": "count",
        "env": lambda c: {"data": tuple(i % 251 for i in range(70)), "buf": tuple([0] * 256), "count": c},
        "domain": list(range(0, 256)),
    },
}


def source(path: str, commit: str, repo: str) -> str:
    cached = evidence.SourceCache(CACHE).get(repo, commit, path, legacy=CACHE / commit / path)
    return cached.read_text(encoding="utf-8")


def cut(text: str, start: str, end: str | None) -> str:
    """The lines from the one containing `start` through the one containing `end` (verbatim)."""
    lines = text.splitlines()
    hits = [i for i, ln in enumerate(lines) if start in ln]
    if len(hits) != 1:
        raise ValueError(f"start marker {start!r} found {len(hits)} times")
    i = hits[0]
    if end is None:
        return lines[i]
    indent = len(lines[i]) - len(lines[i].lstrip("\t"))
    want = int(end[2:]) if end.startswith("}#") else 1                 # "}#2": the second such closing brace
    for j in range(i + 1, len(lines)):
        if end == "}" or end.startswith("}#"):
            if lines[j].strip() == "}" and len(lines[j]) - len(lines[j].lstrip("\t")) <= indent:
                want -= 1
                if want == 0:
                    return "\n".join(lines[i:j + 1])
        elif end in lines[j]:
            return "\n".join(lines[i:j + 1])
    raise ValueError(f"end marker {end!r} not found after {start!r}")


def _require_complete_results(rows: list[tuple], input_count: int, two: bool) -> None:
    if input_count == 0:
        raise RuntimeError("no comparison inputs")
    if len(rows) != input_count:
        raise RuntimeError(f"output error: expected {input_count} rows, got {len(rows)}")
    width = 2 if two else 1
    if any(len(row) != width for row in rows):
        raise RuntimeError(f"output error: expected {width} integer fields per row")


def run_cpp(lines: str, wrap: str, inputs: list[int], two: bool, px4: Path) -> list[tuple]:
    if not inputs:
        raise RuntimeError("no comparison inputs")
    body = wrap.replace("{LINES}", lines)
    if inputs and isinstance(inputs[0], tuple):
        k = len(inputs[0])
        vs = ", ".join(f"v{i}" for i in range(k))
        main = (f"int main() {{ long long {vs}; while (scanf(\"{' '.join(['%lld'] * k)}\", "
                + ", ".join(f"&v{i}" for i in range(k)) + f") == {k}) printf(\"%lld\\n\", run({vs})); return 0; }}\n")
    elif two:
        main = ("int main() { long long x; while (scanf(\"%lld\", &x) == 1) { long long q = 0;"
                " long long r = run(x, &q); printf(\"%lld %lld\\n\", r, q); } return 0; }\n")
    else:
        main = ("int main() { long long x; while (scanf(\"%lld\", &x) == 1) printf(\"%lld\\n\", run(x));"
                " return 0; }\n")
    with tempfile.TemporaryDirectory(prefix="t-px4stmt-") as d:
        cpp, exe = Path(d) / "s.cpp", Path(d) / "s"
        text = "#define PX4_ISFINITE(x) std::isfinite(x)\n" + PRELUDE + body + main
        cpp.write_text(text, encoding="utf-8")
        evidence.wrapper_source(text)
        _run_cpp_process(["g++", *CXX_FLAGS, f"-I{px4}/src/lib", f"-I{px4}/src/lib/matrix",
                          f"-I{px4}/stub", str(cpp), "-o", str(exe)], "compile", timeout=300)
        out = _run_cpp_process([str(exe)], "runtime", input="\n".join(
            " ".join(map(str, v)) if isinstance(v, tuple) else str(v) for v in inputs) + "\n",
            timeout=120).stdout.splitlines()
    try:
        rows = [tuple(int(v) for v in ln.split()) for ln in out]
    except ValueError as error:
        raise RuntimeError(f"output error: invalid integer result: {error}") from error
    _require_complete_results(rows, len(inputs), two)
    return rows


def t_result(task: dict, env0: dict):
    """What t's interpreter gives: the return value, 'undefined', or None outside `requires`."""
    funs = interp.funs_of(task, task["body"])
    if not all(interp.ev(c, env0, funs, interp.St()) for c in task.get("requires", [])):
        return None
    env = dict(env0)
    ret = task["returns"][0]["name"]
    env[ret] = None
    try:
        interp.exec_body(task["body"], env, funs, interp.St())
    except interp.Undef:
        return "undefined"
    return env[ret]


def check(name: str, spec: dict, px4: Path) -> dict:
    finding = tasks_io.load_task(str(HERE / spec["finding"]))
    fix = tasks_io.load_task(str(HERE / spec["fix"]))
    real_in = json.loads((HERE / "findings" / "real_inputs.json").read_text())[finding["name"]]["input"]
    if "params" in spec:                           # several integer parameters, fed as one tuple per input
        ps = spec["params"]
        real = tuple(real_in[q] for q in ps)
        dom = sorted({tuple(env0[q] for q in ps) for env0, _ in interp.Reference(finding).points
                      if all(isinstance(env0[q], int) for q in ps) and spec.get("keep", lambda t: True)(
                          {q: env0[q] for q in ps})} | {real})
        spec = dict(spec, param=None, env=lambda at, ps=ps: dict(zip(ps, at)))
    else:
        real = real_in[spec["param"]]
    if "params" in spec:
        pass
    elif "domain" in spec:
        dom = spec["domain"]
    else:
        dom = sorted({env0[spec["param"]] for env0, _ in interp.Reference(finding).points} | {real})
    if spec.get("param") == "p":                       # a float parameter carries these integers exactly
        dom = [v for v in dom if abs(v) <= 2 ** 24]
    if not dom:
        raise RuntimeError(f"{name}: no comparison inputs")
    two = name == "stream_interval"
    rows = []
    for which, task, commit, repo in (("original", finding, spec.get("pinned", PX4_COMMIT), "PX4/PX4-Autopilot"),
                                      ("fixed", fix, spec["fix_commit"], FORK)):
        lines = cut(source(spec["file"], commit, repo), *spec["orig" if which == "original" else "fixed"])
        wrap = spec.get("wrap_fixed", spec["wrap"]) if which == "fixed" else spec["wrap"]
        evidence.start_case(task["name"], task, dom, "", role=which,
                            task_bytes=(HERE / spec["finding" if which == "original" else "fix"]).read_bytes(),
                            flags=CXX_FLAGS + ["-I<source>/src/lib", "-I<source>/src/lib/matrix", "-I<stub>"])
        got = run_cpp(lines, wrap, dom, two, px4)
        _require_complete_results(got, len(dom), two)
        agree, differ, skipped = 0, [], 0
        for v, g in zip(dom, got):
            px4_val, at = (g[0], g[1]) if two else (g[0], v)
            env0 = spec["env"](at) if "env" in spec else {spec["param"]: at}
            t_val = t_result(task, env0)
            if t_val is None:
                skipped += 1
                continue
            t_shown = -1 if t_val == "undefined" else t_val           # the C program prints -1 for a read past data
            if name == "serial_control" and t_val == "undefined":
                ok = px4_val == -1
            elif name == "serial_control":
                ok = px4_val == t_val
            else:
                ok = px4_val == t_shown
            if ok:
                agree += 1
            else:
                differ.append({"input": at, "px4": px4_val, "t": t_val})
        if len(dom) == skipped:
            raise RuntimeError(f"{name} {which}: no admissible comparison inputs")
        row = {"pair": name, "pr": spec["pr"], "code": which, "task": task["name"],
                     "commit": commit[:12], "lines": lines.count("\n") + 1, "inputs": len(got) - skipped,
                     "agree": agree, "first_difference": differ[0] if differ else None,
                     "real_input": real, "px4_at_real": next((g[0] for v, g in zip(dom, got) if v == real), None)}
        evidence.finish_case(dict(row, status="agrees" if agree == row["inputs"] else "DIFFERS",
                                  returned_rows=len(got), skipped_inputs=skipped))
        rows.append(row)
    return {"name": name, "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="px4_stmt.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--table", metavar="PATH")
    ap.add_argument("--receipt", type=Path, help="write a machine-readable identity and execution receipt")
    args = ap.parse_args(argv)
    with evidence.recording(args.receipt, "px4_statements") as receipt:
        code = _run_comparisons(args)
        if receipt is not None:
            receipt.data.update(exit_code=code, run_outcome="completed" if code == 0 else "failed")
        return code


def _run_comparisons(args) -> int:
    px4 = fetch_px4()
    try:
        results = [check(n, s, px4) for n, s in PAIRS.items()]
    except RuntimeError as error:
        evidence.finish_case({"status": "execution error"})
        print(f"comparison failed: {error}", file=sys.stderr)
        return 1
    if not results:
        print("comparison failed: no statement pairs", file=sys.stderr)
        return 1
    bad = 0
    for r in results:
        for x in r["rows"]:
            ok = x["agree"] == x["inputs"] and x["inputs"] > 0
            bad += not ok
            print(f"{x['pair']} {x['code']} ({x['task']}, {x['commit']}): {x['agree']}/{x['inputs']} agree"
                  + ("" if ok else f"; first difference {json.dumps(x['first_difference'])}"))
    if args.table:
        lines = ["# PX4's own statements against the t findings and fixes", "",
                 "Each handler's lines, cut verbatim from PX4's source at the pinned commit (`original`) and at the "
                 "fix's commit on the pull request's branch (`fixed`), compiled with stand-ins for the surrounding "
                 "names only, and run at every input; t's interpreter runs the finding (original) or the fix at the "
                 "same input (t/flight/px4_stmt.py). x86-64, GCC.", "",
                 "| PR | code | t task | commit | PX4 lines | inputs | agree | at the real input, PX4 gives |",
                 "|---|---|---|---|---|---|---|---|"]
        for r in results:
            for x in r["rows"]:
                lines.append(f"| #{x['pr']} | {x['code']} | {x['task']} | {x['commit']} | {x['lines']} | "
                             f"{x['inputs']} | {x['agree']} | {x['px4_at_real']} at {x['real_input']} |")
        Path(args.table).write_text("\n".join(lines) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
