#!/usr/bin/env python3
"""check_my_computer.py — will this run here, and how fast? Ask the machine.

    python check_my_computer.py          (or double-click "Check My Computer.bat")

Run this once after installing. It checks what you have, times a real training
step on it, and tells you in plain words what you can train and how long it will
take. Everything it says about speed is MEASURED on this computer, not copied
from someone else's.

WHY THIS EXISTS AND WHY IT IS SEPARATE FROM bench_device.py. The studio shows
"about 5 minutes" next to each size, and those numbers come from a benchmark
file. With no benchmark it refuses to guess and says the machine has not been
timed - correct, and useless to someone who just installed it. This produces
that file.

It could not simply BE bench_device.py, for two reasons that only appear at
install time:

  * bench_device.py does `import torch` at the top, so on a machine where torch
    is missing it dies with a traceback instead of saying "torch is missing, here
    is the command". The one moment you most need a clear answer is the moment
    the thing is not installed.
  * bench_device.py times against corpus.txt, and a fresh install has no corpus
    yet. Timing does not depend on WHAT the text says - only on the shapes of
    the tensors - so this builds a small synthetic text and says so.

The timing itself is bench_device.time_steps, imported rather than copied. Two
implementations of "how fast is a step" would drift, and this repo has paid for
a duplicated helper before.
"""
from __future__ import annotations

import ctypes
import json
import platform
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import setup_training                                    # noqa: E402

RESULT = HERE / "bench_device_result.json"
MIN_PYTHON = (3, 10)

# Fewer steps than bench_device uses. This is a "can I run this" check someone
# is waiting on, not a measurement going into a report, and the honest cost is
# that these numbers are noisier - which is why measured_over_steps is recorded
# alongside them exactly as bench_device does.
GPU_STEPS, GPU_WARMUP = 40, 8
CPU_STEPS, CPU_WARMUP = 8, 2

# Enough text to build a tokenizer and fill batches. Content is irrelevant to
# timing; only the tensor shapes matter.
SYNTHETIC = ("The quick brown fox jumps over the lazy dog. "
             "Pack my box with five dozen liquor jugs. "
             "How vexingly quick daft zebras jump! ") * 400


def human(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} seconds"
    if seconds < 5400:
        return f"{seconds / 60:.0f} minutes"
    return f"{seconds / 3600:.1f} hours"


def total_ram_gb() -> float | None:
    """Windows only, via the API; None elsewhere rather than a guess."""
    try:
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MS()
        st.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
        return st.ullTotalPhys / 1e9
    except Exception:                                  # noqa: BLE001
        return None


def line(ok: bool | None, label: str, detail: str = "") -> None:
    mark = {True: "[ok]  ", False: "[!!]  ", None: "[--]  "}[ok]
    print(f"  {mark}{label}" + (f"   {detail}" if detail else ""))


def main() -> int:
    print("=" * 68)
    print("  CHECKING YOUR COMPUTER")
    print("=" * 68)
    print(f"\n{platform.system()} {platform.release()} · "
          f"{platform.processor() or platform.machine()}\n")

    problems, warnings = [], []

    # ---- things that do not need torch -----------------------------------
    v = sys.version_info
    py_ok = (v.major, v.minor) >= MIN_PYTHON
    line(py_ok, f"Python {v.major}.{v.minor}.{v.micro}",
         "" if py_ok else f"needs {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer")
    if not py_ok:
        problems.append(f"Python {v.major}.{v.minor} is too old; install "
                        f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer.")

    try:
        import tkinter                                  # noqa: F401
        line(True, "Graphical window support (Tk)")
    except Exception:                                   # noqa: BLE001
        line(False, "Graphical window support (Tk)", "missing")
        problems.append("Tk is missing, so the studio window cannot open. On "
                        "Windows, reinstall Python with the tcl/tk option "
                        "ticked; on Linux, install python3-tk.")

    ram = total_ram_gb()
    if ram is None:
        line(None, "Memory", "could not be read on this system")
    else:
        line(ram >= 8, f"Memory {ram:.0f} GB",
             "" if ram >= 8 else "8 GB or more is recommended")
        if ram < 8:
            warnings.append(f"{ram:.0f} GB of memory is tight. Prefer the Small "
                            f"size and a corpus under 100 MB.")

    free = shutil.disk_usage(HERE).free / 1e9
    line(free >= 3, f"Free disk space {free:.0f} GB",
         "" if free >= 3 else "a corpus and a model need about 3 GB")
    if free < 3:
        warnings.append(f"Only {free:.0f} GB free. The recommended corpus "
                        f"download alone is 200 MB.")

    # ---- torch, guarded --------------------------------------------------
    try:
        import torch
    except ImportError:
        line(False, "PyTorch", "not installed")
        print("\n" + "=" * 68)
        print("  CANNOT TRAIN YET")
        print("=" * 68)
        print("\nPyTorch is what actually does the training. The easiest way to")
        print("install it is the setup script that comes with this copy:\n")
        print("    python3 setup_training.py\n")
        nvidia = setup_training.nvidia_driver_info()
        if nvidia is not None:
            name, driver = nvidia
            index_url, _reason = setup_training.pick_wheel_index(
                platform.system().lower(), nvidia)
            print(f"You have an NVIDIA {name} (driver {driver}). By hand, that is:\n")
            print(f"    pip install torch --index-url {index_url}\n")
        else:
            print("By hand, that is:\n")
            print("    pip install torch\n")
            print("If you have an NVIDIA graphics card, get the CUDA build instead -")
            print("it is many times faster. See https://pytorch.org for the exact")
            print("command for your machine.\n")
        for p in problems:
            print(f"  also: {p}")
        return 1

    line(True, f"PyTorch {torch.__version__}")

    has_cuda = torch.cuda.is_available()
    has_mps = torch.backends.mps.is_available()
    if has_cuda:
        p = torch.cuda.get_device_properties(0)
        gpu_label = p.name
        line(True, f"Graphics card {p.name}", f"{p.total_memory / 1e9:.1f} GB")
    elif has_mps:
        gpu_label = "Apple silicon (MPS)"
        line(True, "Graphics card Apple silicon",
             f"{torch.mps.recommended_max_memory() / 1e9:.1f} GB usable")
    else:
        gpu_label = None
        nvidia = setup_training.nvidia_driver_info()
        if nvidia is not None:
            name, driver = nvidia
            index_url, _reason = setup_training.pick_wheel_index(
                platform.system().lower(), nvidia)
            line(False, f"Graphics card {name}", f"driver {driver} — PyTorch cannot use it")
            warnings.append(setup_training.unusable_nvidia_message(name, driver, index_url))
        else:
            line(None, "Graphics card", "none usable by PyTorch — will use the CPU")
            warnings.append(
                "No graphics card is being used. Training still works on the "
                "processor, just slower — the timings below are the real ones for "
                "this machine, so trust those rather than the word 'slower'.")

    if problems:
        print("\n" + "=" * 68)
        print("  FIX THESE FIRST")
        print("=" * 68)
        for p in problems:
            print(f"\n  - {p}")
        return 1

    # ---- the measurement -------------------------------------------------
    print("\nTiming a real training step on this machine. This takes a minute...\n")

    import bench_device                                  # noqa: E402
    from data import CharTokenizer, Corpus               # noqa: E402
    from train import enable_fast_math                   # noqa: E402

    enable_fast_math()
    tok = CharTokenizer.from_text(SYNTHETIC)
    devices = ["cpu"] + (["cuda"] if has_cuda else (["mps"] if has_mps else []))
    results = {}
    for device in devices:
        corpus = Corpus(SYNTHETIC, tok, device)
        steps = CPU_STEPS if device == "cpu" else GPU_STEPS
        warmup = CPU_WARMUP if device == "cpu" else GPU_WARMUP
        for name, cfg_d in bench_device.SIZES:
            params, ms, tok_s = bench_device.time_steps(
                corpus, tok, device, cfg_d, steps, warmup)
            results[f"{device}/{name}"] = {
                "params": params, "ms_per_step": round(ms, 2),
                "tokens_per_s": round(tok_s),
                "full_2000_step_s": round(ms * bench_device.FULL_RUN_STEPS / 1000, 1),
                "measured_over_steps": steps}

    # Same schema and same keys bench_device.py writes, because studio.py reads
    # this file to turn its size presets into real times. A second schema would
    # be a second thing to keep in step.
    RESULT.write_text(json.dumps({
        "machine": platform.processor() or platform.machine(),
        "gpu": gpu_label,
        "torch": torch.__version__,
        "full_run_steps": bench_device.FULL_RUN_STEPS,
        "measured_by": "check_my_computer.py (synthetic text, short runs)",
        "results": results}, indent=2), encoding="utf-8")

    # ---- what it means, in words ----------------------------------------
    device = "cuda" if has_cuda else ("mps" if has_mps else "cpu")
    print("=" * 68)
    print("  WHAT YOU CAN TRAIN HERE")
    print("=" * 68)
    print()
    labels = {"small": "Small ", "default": "Medium", "large": "Large "}
    for name, _ in bench_device.SIZES:
        r = results[f"{device}/{name}"]
        five_min_steps = int(300 / (r["ms_per_step"] / 1000))
        print(f"  {labels[name]}  {r['params'] / 1e6:5.2f}M numbers   "
              f"{human(300):>10} of training = {five_min_steps:,} practice steps")

    print()
    slow = results[f"{device}/large"]["ms_per_step"]
    if slow > 400:
        print("  RECOMMENDED: Small or Medium. Large is slow enough on this")
        print("  machine that you will not want to wait for it.")
    else:
        print("  RECOMMENDED: any of the three. Medium is the usual choice.")

    if has_cuda:
        print()
        for name, _ in bench_device.SIZES:
            c = results[f"cpu/{name}"]["ms_per_step"]
            g = results[f"cuda/{name}"]["ms_per_step"]
            print(f"  {labels[name]}  your graphics card is {c / g:.0f}x faster "
                  f"than your processor")

    if warnings:
        print("\n" + "-" * 68)
        for w in warnings:
            print(f"  NOTE: {w}")

    print("\n" + "=" * 68)
    print(f"  Saved to {RESULT.name}. The studio now shows real times for THIS")
    print("  machine instead of saying it has not been timed.")
    print("=" * 68)
    print("\n  Next: double-click \"Train My AI\" to start.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
