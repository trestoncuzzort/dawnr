#!/usr/bin/env python3
"""Read-only lab snapshot for the desktop monitor. No checker or model is started.

Run this on the workstation, optionally through SSH. The JSON contains no host
address or process command lines. Unknown completion totals remain unknown.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import spec_experiment as se

KERNELS = ("dafny", "verus", "spark", "framac", "lean", "rocq", "fstar")
SCRIPTS = {"loop_generate.py": "generate", "spec_experiment.py": "generate",
           "run_par.py": "grade", "loop_train.py": "train",
           "train_distributed.py": "train", "train.py": "train"}
CORE_SCRIPTS = {"train_distributed.py", "train.py"}
MAX_TAIL = 16384
MAX_EVENTS = 2 * 1024 * 1024


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {} if default is None else default


def tail(path: Path, limit: int = MAX_TAIL, lines: int = 30) -> str:
    try:
        with path.open("rb") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                return ""
            f.seek(max(0, os.fstat(f.fileno()).st_size - limit))
            text = f.read(limit).decode("utf-8", errors="replace")
        text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text)
        return "\n".join(text.replace("\r", "\n").splitlines()[-lines:])
    except OSError:
        return ""


def flag(argv: list[str], name: str) -> str:
    for i, arg in enumerate(argv):
        if arg.startswith(name + "="):
            return arg.split("=", 1)[1]
        if arg == name and i + 1 < len(argv):
            return argv[i + 1]
    return ""


def relative_path(value: str, cwd: Path) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else cwd / p


def expected_answers(argv: list[str], cwd: Path) -> int | None:
    """Only explicit requested IDs establish a total; a partial raw folder does not."""
    ids = set()
    try:
        source = flag(argv, "--ids-file")
        text = relative_path(source, cwd).read_text() if source else ""
        text += "," + flag(argv, "--ids")
        ids = {int(x) for x in re.split(r"[,\s]+", text) if x}
        only = flag(argv, "--only-heldout")
        if only:
            saved = read_json(relative_path(only, cwd))
            held = set(saved.get("heldout_task_ids") or saved.get("heldout") or [])
            ids = ids & held if ids else held
        if not ids:
            return None
        minimum = flag(argv, "--min-id")
        if minimum:
            ids = {x for x in ids if x >= int(minimum)}
        limit = int(flag(argv, "--limit") or 0)
        return min(len(ids), limit) if limit > 0 else len(ids)
    except (OSError, ValueError, TypeError):
        return None


def count_set(directory: Path) -> dict:
    """Count exact seven-kernel proofs and explicit test results, including zero-pass sets."""
    ext, tests = read_json(directory / "extract.json"), read_json(directory / "tests.json")
    ext = ext if isinstance(ext, dict) else {}
    tests = tests if isinstance(tests, dict) else {}
    outcomes = {v["name"]: v.get("overall") for v in tests.values()
                if isinstance(v, dict) and v.get("name")}
    try:
        cols, rows = se.parse_kernel_table(directory / "kernels.md")
    except (OSError, ValueError):
        cols, rows = [], {}
    raw_files = [p for p in (directory / "raw").glob("*.json") if p.is_file()]
    changed = []
    for path in [directory / "raw", directory / "extract.json", directory / "tests.json",
                 directory / "kernels.md"]:
        try:
            changed.append(path.stat().st_mtime)
        except OSError:
            pass
    result = {"answers": len(raw_files), "updated": max(changed, default=0),
              "total": None,
              "tasks": sum(1 for e in ext.values() if isinstance(e, dict) and e.get("stage") == "task"),
              "passed": sum(v == "pass" for v in outcomes.values()), "graded": len(rows),
              "clean": 0, "wrong": 0, "problems": [], "kernels": len(cols)}
    problems = set()
    for name, row in rows.items():
        if not all(k in cols and row.get(k) == "verified / refuted" for k in KERNELS):
            continue
        outcome = outcomes.get(name)
        if outcome == "pass":
            result["clean"] += 1
            problems.add(name.split("__", 1)[0])
        elif outcome in {"fail", "signature", "requires-excluded", "undefined"}:
            result["wrong"] += 1
    result["problems"] = sorted(problems)
    return result


def process_start(proc: Path, boot: float, ticks: int) -> float:
    text = (proc / "stat").read_text()
    fields = text[text.rfind(")") + 2:].split()
    return boot + int(fields[19]) / ticks


def process_runs(root: Path, proc_root: Path = Path("/proc"), uid: int | None = None) -> list[dict]:
    """Inspect actual Python argv; a shell quoting a command is never a running job."""
    uid = os.getuid() if uid is None else uid
    try:
        boot = next(float(line.split()[1]) for line in (proc_root / "stat").read_text().splitlines()
                    if line.startswith("btime "))
    except (OSError, ValueError, StopIteration):
        boot = 0.0
    ticks = os.sysconf("SC_CLK_TCK")
    runs = []
    for proc in proc_root.iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            if proc.stat().st_uid != uid:
                continue
            argv = (proc / "cmdline").read_bytes().decode(errors="replace").rstrip("\0").split("\0")
            if not re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", Path(argv[0]).name):
                continue
            # -c workers and shells often carry a script name inside a string.
            if "-c" in argv[:3] or "-m" in argv[:3]:
                continue
            script = next((a for a in argv[1:] if not a.startswith("-")), "")
            script_name = Path(script).name
            if script_name not in SCRIPTS:
                continue
            script_index = argv.index(script)
            if script_name == "spec_experiment.py" and argv[script_index + 1:script_index + 2] != ["generate"]:
                continue
            cwd = (proc / "cwd").resolve(strict=True)
            script_dir = "locallm" if script_name in CORE_SCRIPTS else "t"
            if relative_path(script, cwd).resolve() != root / script_dir / script_name:
                continue
            kind = SCRIPTS[script_name]
            tag = flag(argv, "--tag")
            if not tag and script_name == "spec_experiment.py":
                tag = flag(argv, "--model")
            if not tag and kind == "grade":
                tasks = flag(argv, "--tasks")
                tag = Path(tasks).parent.name if tasks else "committed tasks"
            if not tag and kind == "train":
                tag = Path(flag(argv, "--out") or "training").name
            log = ""
            output = (proc / "fd" / "1").resolve()
            if output.is_relative_to(root) and output.is_file():
                log = tail(output)
            progress = ["", None]
            if script_name == "train_distributed.py":
                destination = flag(argv, "--out") or "locallm/out/distributed"
                metadata = read_json(relative_path(destination, cwd) / "run.json")
                completed = metadata.get("completed_steps", 0)
                total = metadata.get("identity", {}).get("training", {}).get("steps")
                if isinstance(completed, int) and isinstance(total, int) and total > 0:
                    progress = [f"{completed} of {total} training steps", min(1.0, completed / total)]
            runs.append({"key": f"run:{proc.name}", "title": f"{kind.capitalize()}: {tag}",
                         "kind": kind, "tag": tag, "pid": int(proc.name),
                         "started": process_start(proc, boot, ticks), "log": log,
                         "total": expected_answers(argv, cwd) if kind == "generate" else None,
                         "answers": None, "progress": progress,
                         "_argv": argv, "_cwd": cwd, "_script": script_name})
        except (OSError, ValueError, IndexError):
            continue
    # Each torchrun rank is a real Python process, but they form one training run.
    grouped = {}
    result = []
    for run in sorted(runs, key=lambda r: (r["started"], r["pid"])):
        if run["_script"] != "train_distributed.py":
            result.append(run)
            continue
        destination = relative_path(flag(run["_argv"], "--out") or "locallm/out/distributed", run["_cwd"]).resolve()
        if destination not in grouped:
            run["workers"] = 1
            grouped[destination] = run
            result.append(run)
        else:
            grouped[destination]["workers"] += 1
    for run in grouped.values():
        run["title"] += f" ({run['workers']} ranks)"
    return result


def load_steps(root: Path) -> list:
    steps = read_json(root / "t" / "steps.json", [])
    return [r for r in steps if isinstance(r, list) and len(r) >= 6] if isinstance(steps, list) else []


def step_tokens(step: list) -> list[str]:
    try:
        return shlex.split(step[3])
    except (ValueError, TypeError):
        return []


def match_step(run: dict, steps: list) -> list | None:
    for step in steps:
        tokens = step_tokens(step)
        if run["_script"] not in {Path(t).name for t in tokens}:
            continue
        for name in ("--tag", "--out", "--table", "--tasks", "--model"):
            expected = flag(tokens, name)
            actual = flag(run["_argv"], name)
            if expected and actual and "$" not in expected:
                if expected == actual:
                    return step
                # Tags identify a run more narrowly than a shared model name.
                break
    return None


def pool_text(root: Path) -> str:
    base = root / "t" / "out"
    text = []
    for pattern in ("sft-*.jsonl", "pairs-*.jsonl"):
        for path in sorted((base / "loop").glob(pattern)):
            try:
                with path.open() as f:
                    n = sum(bool(line.strip()) for line in f)
                text.append(f"{n:>6}  {path.name}")
            except OSError:
                continue
    scores = list(base.glob("score-r*.md"))
    if scores:
        def round_number(path):
            match = re.search(r"score-r(\d+)", path.name)
            return int(match[1]) if match else -1
        latest = max(scores, key=round_number)
        text.extend(("", latest.name + ":", tail(latest, 12000, 60)))
    return "\n".join(text) or "No pool or score table yet."


def event_snapshot(path: Path, proc_root: Path, cursor: dict | None = None) -> dict:
    empty = {"cursor": {"inode": "", "offset": 0}, "items": [], "active": []}
    try:
        with path.open("rb") as f:
            st = os.fstat(f.fileno())
            inode = f"{st.st_dev}:{st.st_ino}"
            base = max(0, st.st_size - MAX_EVENTS)
            f.seek(base)
            data = f.read(MAX_EVENTS)
        if base:
            drop = data.find(b"\n") + 1
            base, data = base + drop, data[drop:]
        keep = data.rfind(b"\n") + 1
        data = data[:keep]
        end = base + keep
        since = base
        if cursor and cursor.get("inode") == inode:
            offset = int(cursor.get("offset", 0))
            if base <= offset <= end:
                since = offset
        active, ended = {}, []
        position = base
        for line in data.splitlines(keepends=True):
            position += len(line)
            try:
                ev = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(ev, dict) or not isinstance(ev.get("t"), (int, float)):
                continue
            key = (ev.get("pid"), ev.get("task"), ev.get("kernel"))
            if ev.get("ev") == "start":
                active[key] = ev
            elif ev.get("ev") == "end":
                active.pop(key, None)
                if position > since:
                    ended.append(ev)
        alive = []
        boot = next((float(line.split()[1]) for line in (proc_root / "stat").read_text().splitlines()
                     if line.startswith("btime ")), 0.0)
        for ev in active.values():
            pid = ev.get("pid")
            if not isinstance(pid, int):
                continue
            proc = proc_root / str(pid)
            try:
                if (proc.stat().st_uid == os.getuid()
                        and process_start(proc, boot, os.sysconf("SC_CLK_TCK")) <= ev["t"] + 1):
                    alive.append(ev)
            except (OSError, ValueError, IndexError):
                continue
        return {"cursor": {"inode": inode, "offset": end}, "items": ended[-300:], "active": alive}
    except (OSError, ValueError, TypeError):
        return empty


def gpu_snapshot() -> list[dict]:
    try:
        p = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used,memory.total,utilization.gpu",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
        if p.returncode:
            return []
        return [dict(zip(("index", "used_mb", "total_mb", "utilization"),
                         [int(x.strip()) for x in line.split(",")]))
                for line in p.stdout.splitlines() if len(line.split(",")) == 4]
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def followup_snapshot(root: Path, proc_root: Path) -> tuple[dict, list[str]]:
    """Recovery status is a waiting CPU coordinator, never a GPU generation job."""
    paths = sorted((root / "t/runs").glob("*/logs/finish-existing-status.json"))
    if not paths:
        return {}, []
    raw = read_json(paths[-1])
    if not isinstance(raw, dict) or not raw:
        return {}, ["Automatic follow-up status could not be read."]
    pid = raw.get("pid")
    alive = False
    if isinstance(pid, int):
        try:
            proc = proc_root / str(pid)
            argv = (proc / "cmdline").read_bytes().decode(errors="replace").split("\0")
            alive = (proc.stat().st_uid == os.getuid()
                     and re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", Path(argv[0]).name) is not None
                     and any(Path(a).name == "finish_existing.py" for a in argv[1:3]))
        except (OSError, ValueError):
            pass
    age = None
    try:
        heartbeat = datetime.fromisoformat(str(raw.get("heartbeat", "")).replace("Z", "+00:00"))
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=timezone.utc)
        age = max(0, time.time() - heartbeat.timestamp())
    except ValueError:
        pass
    tags = {tag: {key: value for key, value in entry.items()
                  if key in ("raw", "expected", "generating", "state", "step", "reason", "completed", "last_exit")}
            for tag, entry in raw.get("tags", {}).items() if isinstance(entry, dict)}
    result = {"alive": alive, "pid": pid, "heartbeat": raw.get("heartbeat"), "age": age,
              "jobs": raw.get("jobs"), "tags": tags,
              "log": tail(paths[-1].parent / "finish-existing.log", lines=15)}
    warnings = []
    finished = bool(tags) and all(t.get("state") == "complete" for t in tags.values())
    if not alive and not finished:
        warnings.append("Automatic follow-up worker is not running; unfinished answer sets will need attention.")
    elif alive and (age is None or age > 120):
        warnings.append("Automatic follow-up heartbeat is stale; check its output.")
    for tag, entry in tags.items():
        if entry.get("state") in {"failed", "blocked"}:
            warnings.append(f"{tag}: {entry['state']} — {entry.get('reason', 'check follow-up output')}")
    return result, warnings


def snapshot(root: Path | None = None, proc_root: Path = Path("/proc"), uid: int | None = None,
             include_gpu: bool = True, events_cursor: dict | None = None,
             events_path: Path | None = None) -> dict:
    root = (root or Path(__file__).resolve().parent.parent).resolve()
    steps = load_steps(root)
    runs = process_runs(root, proc_root, uid)
    states = {s[0]: {"state": "", "progress": ["", None]} for s in steps}
    sets, problems = [], set()
    totals = {k: 0 for k in ("answers", "tasks", "passed", "graded", "clean", "wrong")}
    for directory in sorted((root / "t" / "out" / "spec-experiment").glob("*")):
        if not directory.is_dir():
            continue
        result = count_set(directory)
        if not any(result[k] for k in totals):
            continue
        # An inactive set can still have an explicit ID list in its recorded step.
        for step in steps:
            tokens = step_tokens(step)
            if flag(tokens, "--tag") == directory.name:
                result["total"] = expected_answers(tokens, root)
                break
        sets.append([directory.name, result])
        problems.update(result["problems"])
        for key in totals:
            totals[key] += result[key]
    by_tag = dict(sets)
    for run in runs:
        step = match_step(run, steps)
        if step:
            run["key"], run["title"] = step[:2]
        if run["kind"] == "generate":
            result = by_tag.get(run["tag"], {})
            run["answers"] = result.get("answers", 0)
            if run["total"] is not None:
                result["total"] = run["total"]
            n, total = run["answers"], run["total"]
            run["progress"] = [f"{n} of {total} answers" if total is not None else f"{n} answers",
                               min(1.0, n / total) if total else None]
        states[run["key"]] = {"state": "running", "progress": run["progress"]}
        for private in ("_argv", "_cwd", "_script"):
            run.pop(private)
    for step in steps:
        if states[step[0]]["state"] == "running":
            continue
        tokens = step_tokens(step)
        result = by_tag.get(flag(tokens, "--tag"))
        if result and result["total"] is not None:
            n, total = result["answers"], result["total"]
            states[step[0]] = {"state": "done" if n >= total else "",
                               "progress": [f"{n} of {total} answers", min(1.0, n / total) if total else None]}
    events_path = events_path or Path(os.environ.get("T_WATCH", Path.home() / ".cache/t-watch/events.jsonl"))
    followup, warnings = followup_snapshot(root, proc_root)
    return {"version": 1, "time": time.time(), "runs": runs, "steps": states,
            "results": {"sets": sets, "totals": totals, "n_problems": len(problems), "text": pool_text(root)},
            "events": event_snapshot(events_path, proc_root, events_cursor),
            "gpus": gpu_snapshot() if include_gpu else [], "followup": followup, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--events-cursor", type=json.loads)
    parser.add_argument("--no-gpu", action="store_true")
    args = parser.parse_args()
    print(json.dumps(snapshot(args.repo, include_gpu=not args.no_gpu, events_cursor=args.events_cursor)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
