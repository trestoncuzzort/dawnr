#!/usr/bin/env python3
"""t/flight/px4_diff.py: PX4's own code against its t transcription, on every domain point.

Each task in this directory restates one PX4 function (README.md names the file, line and instantiation). This harness
fetches PX4's headers at the pinned commit, compiles PX4's own function in a C++ program that calls it on every input
in the task's bounded domain (at most POINTS), and compares each result with t's interpreter running the t task. A
match says the t program computes what PX4 computes there, so what the kernels prove about the t program is about
PX4's function on those inputs. A mismatch is reported with its input.

Integer templates are instantiated at int64_t (the domain reaches beyond int32). The float ones are instantiated at
double, t's binary64; PX4 flies most of them at float. The slew-rate and alpha-filter wrappers pass `dt` and `alpha`
through `float`, as PX4's own signatures do. The specialised `negate<int16_t>` is called at int16_t. Built with
`-ffp-contract=off`, so each double operation rounds once, as t's semantics says.

  python3 t/flight/px4_diff.py [--table PX4-DIFF.md]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import harness  # noqa: E402
import interp  # noqa: E402
import tasks_io  # noqa: E402

PX4_COMMIT = "dd804e4b9c490aed051bb36f8d3fca1ee137be2a"
POINTS = 400
CACHE = HERE.parent / "out" / "px4" / PX4_COMMIT
HEADERS = ["src/lib/mathlib/mathlib.h", "src/lib/mathlib/math/Functions.hpp", "src/lib/mathlib/math/Limits.hpp",
           "src/lib/mathlib/math/SearchMin.hpp", "src/lib/mathlib/math/TrajMath.hpp",
           "src/lib/mathlib/math/Utilities.hpp", "src/lib/mathlib/math/filter/AlphaFilter.hpp",
           "src/lib/slew_rate/SlewRate.hpp", "src/lib/hysteresis/hysteresis.h", "src/lib/hysteresis/hysteresis.cpp",
           "src/lib/collision_prevention/ObstacleMath.hpp", "src/lib/collision_prevention/ObstacleMath.cpp",
           "src/lib/ringbuffer/Ringbuffer.hpp", "src/lib/ringbuffer/Ringbuffer.cpp"]
SOURCES = ["src/lib/hysteresis/hysteresis.cpp", "src/lib/collision_prevention/ObstacleMath.cpp",
           "src/lib/ringbuffer/Ringbuffer.cpp"]
# Ringbuffer keeps `_start` and `_end` private and says nothing of them through its methods but `space_used()`. Every
# translation unit is built with `private` defined as `public`, which changes access only, never code or layout, so
# the harness can set a state the task's `requires` admits and read the indices PX4's code leaves behind.
ACCESS = ["-Dprivate=public"]
MATRIX = ["AxisAngle", "Dcm", "Dcm2", "Dual", "Euler", "LeastSquaresSolver", "Matrix", "PseudoInverse", "Quaternion",
          "Scalar", "Slice", "SparseVector", "SquareMatrix", "Vector", "Vector2", "Vector3", "Vector4", "filter",
          "helper_functions", "integration", "math"]
STUB = ("// Stand-in for PX4's platform header: only the names the math headers use.\n#pragma once\n#include <cmath>\n"
        "#define PX4_ISFINITE(x) std::isfinite(x)\n#define M_TWOPI_F 6.28318530717958647692f\n"
        "#define M_PI_F 3.14159265358979323846f\n")
HRT_STUB = ("// Stand-in for PX4's timer header: only the type hysteresis.h uses.\n#pragma once\n#include <cstdint>\n"
            "typedef uint64_t hrt_abstime;\n")
# A Hysteresis in a given (state, requested, last) reached through PX4's public API only: construct at `state`; with
# the hysteresis time from `state` at INT64_MAX, set_state_and_update(requested, last) records the request and its
# time and cannot switch (last + INT64_MAX does not wrap for last < 2^63); then the task's own times are set.
_HYST_PRE = ("systemlib::Hysteresis h(state); h.set_hysteresis_time_from(state, (hrt_abstime)INT64_MAX); "
             "h.set_state_and_update(requested, (hrt_abstime)last); "
             "h.set_hysteresis_time_from(true, (hrt_abstime)time_from_true); "
             "h.set_hysteresis_time_from(false, (hrt_abstime)time_from_false); ")
_HYST_RUN = ("systemlib::Hysteresis h; h.set_hysteresis_time_from(true, (hrt_abstime)time_from_true); "
             "h.set_hysteresis_time_from(false, (hrt_abstime)time_from_false); "
             "for (size_t i = 0; i < times.size(); i++) h.set_state_and_update({new}, (hrt_abstime)times[i]); ")

# task -> (C++ expression calling PX4 on the parameters, result kind)
CALLS = {
    "px4_constrain": ("math::constrain<int64_t>(val, min_val, max_val)", "int"),
    "px4_min": ("math::min<int64_t>(a, b)", "int"),
    "px4_max": ("math::max<int64_t>(a, b)", "int"),
    "px4_min3": ("math::min<int64_t>(a, b, c)", "int"),
    "px4_max3": ("math::max<int64_t>(a, b, c)", "int"),
    "px4_is_in_range": ("math::isInRange<int64_t>(val, min_val, max_val)", "bool"),
    "px4_sign_no_zero": ("math::signNoZero<int64_t>(val)", "int"),
    "px4_sign": ("matrix::sign<int64_t>(val)", "int"),
    "px4_sign_from_bool": ("math::signFromBool(positive)", "int"),
    "px4_sq": ("math::sq<int64_t>(val)", "int"),
    "px4_negate_i16": ("math::negate<int16_t>((int16_t)value)", "int"),
    "px4_wrap_int": ("matrix::wrap<int64_t>(x, low, high)", "int"),
    "px4_constrain_f": ("math::constrain<double>(val, min_val, max_val)", "float"),
    "px4_lerp": ("math::lerp<double>(a, b, s)", "float"),
    "px4_interpolate": ("math::interpolate<double>(value, x_low, x_high, y_low, y_high)", "float"),
    "px4_slew_update": ("[&]{ SlewRate<double> sr(value); sr.setSlewRate(slew_rate); "
                        "return sr.update(new_value, (float)dt); }()", "float"),
    "px4_alpha_update": ("[&]{ AlphaFilter<double> f; f.setAlpha((float)alpha); f.reset(state); "
                         "return f.update(sample); }()", "float"),
    "px4_hysteresis_update": ("[&]{ " + _HYST_PRE + "h.update((hrt_abstime)now); return h.get_state(); }()", "bool"),
    "px4_hysteresis_set": ("[&]{ " + _HYST_PRE + "h.set_state_and_update(new_state, (hrt_abstime)now); "
                           "return h.get_state(); }()", "bool"),
    "px4_hysteresis_holds": ("[&]{ " + _HYST_RUN.format(new="news[i] != 0") + "return h.get_state(); }()", "bool"),
    "px4_hysteresis_switches": ("[&]{ " + _HYST_RUN.format(new="true") + "return h.get_state(); }()", "bool"),
    "px4_wrap_bin": ("ObstacleMath::wrap_bin((int)bin, (int)bin_count)", "int"),
    "px4_wrap_bin_72": ("ObstacleMath::wrap_bin((int)bin, 72)", "int"),
    "px4_rb_space_available": ("[&]{ Ringbuffer b; b.allocate((size_t)size); b._start = (size_t)start; "
                               "b._end = (size_t)end; return b.space_available(); }()", "int"),
    "px4_rb_push_back": ("[&]{ Ringbuffer b; b.allocate((size_t)size); b._start = (size_t)start; b._end = (size_t)end; "
                         "std::vector<uint8_t> src((size_t)buf_len + 1); "
                         "bool ok = b.push_back(src.data(), (size_t)buf_len); "
                         "return std::make_pair((long long)ok, (long long)b._end); }()", "pair"),
    "px4_rb_pop_front": ("[&]{ Ringbuffer b; b.allocate((size_t)size); b._start = (size_t)start; b._end = (size_t)end; "
                         "std::vector<uint8_t> dst((size_t)buf_max_len + 1); "
                         "size_t n = b.pop_front(dst.data(), (size_t)buf_max_len); "
                         "return std::make_pair((long long)n, (long long)b._start); }()", "pair"),
}
FIXES = HERE / "fixes"
# a task under fixes/ restates the change proposed to PX4 for a finding; with --fixed-tree, the patched PX4 checkout's
# own code is compiled and run against it, through the call of the function it replaces
FIX_OF = {"px4_wrap_bin_fixed": "px4_wrap_bin", "px4_wrap_bin_fixed_72": "px4_wrap_bin_72"}
# the handler needs a running module, so its own statements are cut from PX4's source and run instead
STMT = "the handler's own statements, before and after the fix, compiled and run on every input: px4_stmt.py, PX4-STMT.md"
# fixes and findings checked against PX4 by another route than this harness's per-point call, with the route named
FIX_NOT_DIFFED = {
    "px4_request_event_fixed": STMT,
    "px4_arm_param_fixed": STMT,
    "px4_stream_interval_fixed": STMT,
    "px4_do_jump_index_fixed": STMT,
    "px4_serial_control_fixed": STMT,
    "px4_set_mode_field_fixed": STMT,
    "px4_fusion_source_fixed": STMT,
    "px4_obstacle_body_fixed": "CollisionPrevention::_addObstacleSensorData needs the collision-prevention module; checked by PX4's own test, CollisionPreventionTest.addObstacleSensorData_bodyframe_fine_increment: it fails 50 assertions on the original code and passes with the fix (PR #29037)",
    "px4_sumd_receive_fixed": "sumd_decode is a byte-at-a-time state machine; the patched sumd.cpp was "
                  "run on a valid 32-channel frame and PX4's recorded stream under UBSan (README)"}
FINDINGS = HERE / "findings"
# a task under findings/ restates a PX4 function with the contract it needs and without the `requires` PX4's callers
# do not establish; the kernels refute it, and PX4's own code is run at the refuting input and at the probes below
FINDING_OF = {"px4_wrap_bin_any": "px4_wrap_bin"}
PROBES = {"px4_wrap_bin_any": [{"bin": -73, "bin_count": 72}]}
FINDING_NOT_RUN = {
    "px4_request_event_any": STMT,
    "px4_arm_param_any": STMT,
    "px4_stream_interval_any": STMT,
    "px4_do_jump_index_any": STMT,
    "px4_serial_control_any": STMT,
    "px4_set_mode_field_any": STMT,
    "px4_fusion_source_any": STMT,
    "px4_obstacle_body_any": "CollisionPrevention::_addObstacleSensorData needs the collision-prevention module; checked by PX4's own test, CollisionPreventionTest.addObstacleSensorData_bodyframe_fine_increment: it fails 50 assertions on the original code and passes with the fix (PR #29037)",
    "px4_sumd_receive_any": "PX4's own sumd.cpp, built with UBSan, reports the out-of-bounds write "
                   "and read at index 64 on a valid 32-channel frame (README)"}
# parameters PX4's own signature narrows to binary32 (`float`) before use, though the template is at double
NARROWED = {"px4_alpha_update": ["alpha"], "px4_slew_update": ["dt"]}

NOT_DIFFED = {"px4_interp_index": "the index is internal to interpolateNXY, which returns only the interpolated value"}


def fetch_px4() -> Path:
    """PX4's headers at the pinned commit, cached; the platform header replaced by STUB."""
    root = CACHE
    files = HEADERS + [f"src/lib/matrix/matrix/{m}.hpp" for m in MATRIX] + ["LICENSE"]
    for f in files:
        dst = root / f
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://raw.githubusercontent.com/PX4/PX4-Autopilot/{PX4_COMMIT}/{f}"
            with urllib.request.urlopen(url, timeout=60) as r:
                dst.write_bytes(r.read())
    for rel, text in (("px4_platform_common/defines.h", STUB), ("drivers/drv_hrt.h", HRT_STUB)):
        stub = root / "stub" / rel
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text(text)
    return root


def _cpp_type(ty) -> str:
    if ty == "seq":
        return "std::vector<int64_t>"
    if isinstance(ty, dict) and "seq" in ty:
        return f"std::vector<{_cpp_type(ty['seq'])}>"
    return {"float": "double", "bool": "bool"}.get(ty, "int64_t")


def _cpp_lit(v, ty) -> str:
    if ty == "seq" or (isinstance(ty, dict) and "seq" in ty):
        elem = "int" if ty == "seq" else ty["seq"]
        return "{" + ", ".join(_cpp_lit(x, elem) for x in v) + "}"
    if ty == "bool":
        return "true" if v else "false"
    if ty == "float":
        return f"{float(v).hex()}"
    return f"INT64_C({int(v)})"


def program(task: dict, ref, call: str | None = None, pts: list | None = None) -> tuple[str, list, list]:
    expr, kind = CALLS[call or task["name"]]
    pts = ref.points[:POINTS] if pts is None else pts
    lines, expect, inputs = [], [], []
    for env0, real in pts:
        decl = " ".join(f"{_cpp_type(p['type'])} {p['name']} = {_cpp_lit(env0[p['name']], p['type'])};"
                        for p in task["params"])
        if kind == "float":
            show = f'printf("%a\\n", (double)({expr}));'
            expect.append(float(real).hex())
        elif kind == "pair":
            show = (f'auto t_pair = ({expr}); '
                    'printf("%lld %lld\\n", (long long)t_pair.first, (long long)t_pair.second);')
            expect.append(f"{int(real.a)} {int(real.b)}")
        else:
            show = f'printf("%lld\\n", (long long)({expr}));'
            expect.append(str(int(real)))
        lines.append(f"  {{ {decl} {show} }}")
        inputs.append({k: interp._j(v) for k, v in env0.items()})
    src = ("#include <cinttypes>\n#include <cstdio>\n#include <vector>\n#include <mathlib/mathlib.h>\n"
           "#include <matrix/math.hpp>\n#include <slew_rate/SlewRate.hpp>\n"
           "#include <mathlib/math/filter/AlphaFilter.hpp>\n#include <hysteresis/hysteresis.h>\n"
           "#include <collision_prevention/ObstacleMath.hpp>\n#include <ringbuffer/Ringbuffer.hpp>\n"
           "#include <utility>\n"
           "int main() {\n" + "\n".join(lines) + "\n  return 0;\n}\n")
    return src, expect, inputs


def _compile_run(src: str, px4: Path, stub: Path | None = None) -> tuple[list[str] | None, str]:
    stub = stub or px4 / "stub"
    with tempfile.TemporaryDirectory(prefix="t-px4-") as d:
        cpp, exe = Path(d) / "p.cpp", Path(d) / "p"
        cpp.write_text(src)
        p = subprocess.run(["g++", "-std=c++17", "-O1", "-ffp-contract=off", "-w", f"-I{px4}/src/lib",
                            f"-I{px4}/src/lib/matrix", f"-I{stub}", *ACCESS, str(cpp)]
                           + [str(px4 / f) for f in SOURCES] + ["-o", str(exe)],
                           capture_output=True, text=True, timeout=300)
        if p.returncode != 0:
            return None, "compile error: " + (p.stderr.strip().splitlines() or ["?"])[0][:200]
        return subprocess.run([str(exe)], capture_output=True, text=True, timeout=60).stdout.splitlines(), ""


def finding(path: Path, px4: Path) -> dict:
    """A findings/ task: the interpreter's refuting input (harness.real_witness, the input every kernel's refutation
    certificate replays) and the PROBES, each run through PX4's own code. The finding stands when PX4 returns there
    what t's body returns and that value breaks the contract."""
    task = tasks_io.load_task(str(path))
    name, call = task["name"], FINDING_OF[task["name"]]
    harness._set_ctx(task)
    ref = interp.Reference(task)
    w = harness.real_witness(task)
    envs = ([{p["name"]: w[p["name"]] for p in task["params"]}] if w else []) + PROBES.get(name, [])
    funs = interp.funs_of(task, task["body"])
    pts, broken = [], []
    for env0 in envs:
        env = ref._start(dict(env0))
        interp.exec_body(task["body"], env, funs, interp.St())
        pts.append((env0, env[ref.ret]))
        broken.append(not all(interp.ev(c, env, funs, interp.St()) for c in task["ensures"]))
    src, expect, inputs = program(task, ref, call, pts)
    got, err = _compile_run(src, px4)
    if got is None:
        return {"name": name, "px4_call": CALLS[call][0], "status": err}
    rows = [{"input": i, "t": e, "px4": g, "breaks_contract": b} for i, e, g, b in zip(inputs, expect, got, broken)]
    ok = len(got) == len(expect) and all(r["t"] == r["px4"] and r["breaks_contract"] for r in rows)
    return {"name": name, "px4_call": CALLS[call][0], "rows": rows,
            "status": "PX4 breaks the contract here, as t's body does" if ok else "NOT REPRODUCED"}


def diff_fix(path: Path, tree: Path, stub: Path) -> dict:
    """A fixes/ task against the patched PX4 checkout `tree`: every domain point, as diff_task does."""
    task = tasks_io.load_task(str(path))
    name, call = task["name"], FIX_OF[task["name"]]
    harness._set_ctx(task)
    ref = interp.Reference(task)
    src, expect, inputs = program(task, ref, call, ref.points[:POINTS])
    out, err = _compile_run(src, tree, stub)
    if out is None:
        return {"name": name, "status": err}
    bad = [i for i, (e, g) in enumerate(zip(expect, out)) if e != g.strip()]
    res = {"name": name, "points": len(expect), "px4_call": CALLS[call][0]}
    if bad or len(out) != len(expect):
        i = bad[0] if bad else len(out)
        res.update(status="DIFFERS", first={"input": inputs[i] if i < len(inputs) else None})
    else:
        res["status"] = "agrees"
    return res


def diff_task(path: Path, px4: Path) -> dict:
    task = tasks_io.load_task(str(path))
    name = task["name"]
    if name in NOT_DIFFED:
        return {"name": name, "status": f"not diffed: {NOT_DIFFED[name]}"}
    harness._set_ctx(task)
    ref = interp.Reference(task)
    src, expect, inputs = program(task, ref)
    out, err = _compile_run(src, px4)
    if out is None:
        return {"name": name, "status": err}
    norm = (lambda s: float.fromhex(s).hex()) if CALLS[name][1] == "float" else (lambda s: s.strip())
    got = [norm(x) for x in out]
    bad = [i for i, (e, g) in enumerate(zip(expect, got)) if e != g]
    res = {"name": name, "points": len(expect), "px4_call": CALLS[name][0]}
    if bad and len(got) == len(expect) and task["name"] in NARROWED:
        # every difference explained by PX4's float narrowing: rerun t's interpreter with those parameters rounded to
        # binary32 (as PX4's signature does) at each differing point
        import struct
        funs = interp.funs_of(task, task["body"])
        explained = 0
        for i in bad:
            env0 = dict(ref.points[i][0])
            for n in NARROWED[task["name"]]:
                env0[n] = struct.unpack("f", struct.pack("f", env0[n]))[0]
            env = ref._start(env0)
            interp.exec_body(task["body"], env, funs, interp.St())
            if float(env[ref.ret]).hex() == got[i]:
                explained += 1
        if explained == len(bad):
            res.update(status=f"agrees once PX4's float narrowing of {', '.join(NARROWED[task['name']])} is applied",
                       narrowed_points=len(bad))
            return res
    if len(got) != len(expect) or bad:
        i = bad[0] if bad else len(got)
        res.update(status="DIFFERS", first={"input": inputs[i] if i < len(inputs) else None,
                                             "t": expect[i] if i < len(expect) else None,
                                             "px4": got[i] if i < len(got) else None}, differing=len(bad))
    else:
        res["status"] = "agrees"
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="px4_diff.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--table", metavar="PATH")
    ap.add_argument("--fixed-tree", metavar="DIR", help="a PX4 checkout with the proposed fixes applied: run "
                    "fixes/ against it and nothing else")
    args = ap.parse_args(argv)
    px4 = fetch_px4()
    if args.fixed_tree:
        fixed = [diff_fix(p, Path(args.fixed_tree), px4 / "stub") for p in sorted(FIXES.glob("*.t"))
                 if p.stem not in FIX_NOT_DIFFED]
        for r in fixed:
            print(f"fix {r['name']}: {r['status']}" + (f" ({r['points']} points)" if r.get("points") else ""))
        return 1 if any(r["status"] != "agrees" for r in fixed) else 0
    results = [diff_task(p, px4) for p in sorted(HERE.glob("*.t"))]
    found = [finding(p, px4) for p in sorted(FINDINGS.glob("*.t")) if p.stem not in FINDING_NOT_RUN]
    for r in results:
        print(f"{r['name']}: {r['status']}" + (f" ({r['points']} points)" if r.get("points") else "")
              + (f" first: {json.dumps(r['first'])}" if r.get("first") else ""))
    for r in found:
        print(f"finding {r['name']}: {r['status']}" + "".join(f"\n  {json.dumps(x)}" for x in r.get("rows", [])))
    if args.table:
        agree = [r for r in results if r["status"] == "agrees"]
        lines = ["# PX4's code against its t transcription", "",
                 f"PX4-Autopilot at {PX4_COMMIT}: each routine's own C++ (the call below) compiled and run on every "
                 f"domain point of its t task (at most {POINTS}), each result compared with t's interpreter "
                 "(t/flight/px4_diff.py).", "",
                 f"- routines compared: {sum(1 for r in results if r.get('points'))}; agree on every point: "
                 f"{len(agree)}; points: {sum(r.get('points', 0) for r in results)}", "",
                 "| t task | PX4 call | status | points | first difference |", "|---|---|---|---|---|"]
        for r in results:
            lines.append(f"| {r['name']} | `{r.get('px4_call', '')}` | {r['status']} | {r.get('points', '')} | "
                         f"{json.dumps(r['first']) if r.get('first') else ''} |")
        if found:
            lines += ["", "## Contracts PX4's code breaks", "",
                      "Each task under `t/flight/findings/` restates a PX4 function with its contract and without the "
                      "`requires` its callers do not establish. The input below is where the kernels' refutation "
                      "certificates point (or a probe); PX4's own code is run there.", "",
                      "| t task | PX4 call | input | t | PX4 | breaks the contract | status |",
                      "|---|---|---|---|---|---|---|"]
            for r in found:
                for x in r.get("rows", [{}]):
                    lines.append(f"| {r['name']} | `{r['px4_call']}` | {json.dumps(x.get('input', ''))} | "
                                 f"{x.get('t', '')} | {x.get('px4', '')} | {x.get('breaks_contract', '')} | "
                                 f"{r['status']} |")
        Path(args.table).write_text("\n".join(lines) + "\n")
    return 1 if any(r["status"] == "DIFFERS" for r in results) or any(r["status"] == "NOT REPRODUCED" for r in found) \
        else 0


if __name__ == "__main__":
    sys.exit(main())
