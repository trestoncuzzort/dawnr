"""Read-only study/process probe for an external event-driven completion watcher."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent


def process_identity(pid, script: str, output: Path, *, proc=Path("/proc"), expected_start_ticks=None):
    result = {"pid": pid, "alive": False, "argv_match": False, "start_ticks": None}
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 1:
        return result
    directory = proc / str(pid)
    try:
        if directory.stat().st_uid != os.getuid():
            return result
        fields = (directory / "stat").read_text().rsplit(") ", 1)[1].split()
        result["start_ticks"] = int(fields[19])
        result["alive"] = fields[0] not in ("Z", "X")
        argv = [arg.decode("utf-8", errors="replace") for arg in (directory / "cmdline").read_bytes().split(b"\0") if arg]
        cwd = (directory / "cwd").resolve(strict=True)
        if not argv or not Path(argv[0]).name.startswith("python"):
            return result
        scripts = [((cwd / value) if not Path(value).is_absolute() else Path(value)).resolve()
                   for value in argv[1:] if Path(value).name == script]
        if HERE / script not in scripts or "--out" not in argv:
            return result
        target = Path(argv[argv.index("--out") + 1])
        target = (cwd / target).resolve() if not target.is_absolute() else target.resolve()
        if target != output.resolve():
            return result
        if script == "train_distributed.py" and not any(argv[index:index + 2] == ["-m", "torch.distributed.run"] for index in range(len(argv) - 1)):
            return result
        if expected_start_ticks is not None and result["start_ticks"] != expected_start_ticks:
            return result
        result["argv_match"] = True
    except (OSError, ValueError, IndexError):
        pass
    return result


def relative_file(root: Path, value: str) -> Path:
    path = Path(value)
    resolved = (root / path).resolve()
    if path.is_absolute() or not resolved.is_relative_to(root.resolve()):
        raise ValueError("Study artifact path escapes its output directory")
    return resolved


def read_json(path: Path):
    return json.loads(path.read_bytes().decode("utf-8"))


def latest_metric(path: Path):
    try:
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 65536))
            lines = stream.read().splitlines()
        for line in reversed(lines):
            try:
                value = json.loads(line)
                if isinstance(value.get("step"), int):
                    return value["step"]
            except (ValueError, AttributeError):
                continue
    except OSError:
        pass
    return 0


def newest_mtime(paths):
    times = []
    for path in paths:
        try:
            times.append(path.stat().st_mtime)
        except OSError:
            pass
    return max(times) if times else None


def integrity_issues(output: Path, *, source_dir=HERE):
    """Cross-check recorded evidence independently of the runner's status flags."""
    ledger = read_json(output / "study.json")
    issues = []
    for name, expected in ledger["source_sha256"].items():
        if Path(name).name != name:
            issues.append("invalid_source_name")
            continue
        actual = hashlib.sha256((source_dir / name).read_bytes()).hexdigest()
        if actual != expected:
            issues.append("frozen_source_changed:" + name)
    config = ledger["configuration"]
    expected_tokens = 4 * config["batch_size"] * config["grad_accum"] * config["block_size"]
    for arm in ledger["arms"]:
        root = relative_file(output, arm["out"])
        record_path, metrics_path = root / "run.json", root / "metrics.jsonl"
        if record_path.exists():
            record = read_json(record_path)
            if record.get("tokens_per_step") != expected_tokens:
                issues.append("token_budget_changed:" + arm["id"])
            identity = record.get("identity", {})
            if identity.get("tokenizer_fingerprint") != ledger["inputs"]["tokenizer_fingerprint"]:
                issues.append("tokenizer_identity_changed:" + arm["id"])
            data = identity.get("data", {})
            for key, filename in (("train_sha256", "train.txt"), ("val_sha256", "validation.txt")):
                if data.get(key) != ledger["inputs"]["corpus_artifacts"][filename]:
                    issues.append("data_identity_changed:" + arm["id"])
        if metrics_path.exists():
            content = metrics_path.read_bytes()
            # A live append may end mid-record. Recheck that tail next time.
            lines = content.splitlines()
            if content and not content.endswith(b"\n"):
                lines = lines[:-1]
            previous = -1
            for line in lines:
                row = json.loads(line)
                step = row.get("step")
                if type(step) is not int or step <= previous or step > config["steps"]:
                    issues.append("invalid_metric_step:" + arm["id"])
                    break
                previous = step
                for key in ("train_nats_per_token", "val_nats_per_token"):
                    value = row.get(key)
                    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                        issues.append("invalid_loss:" + arm["id"])
    return sorted(set(issues))


def inspect_study(output: Path, runner_pid: int, *, runner_start_ticks=None, stall_seconds=600,
                  startup_grace_seconds=120, proc=Path("/proc"), now=None):
    now = time.time() if now is None else now
    runner = process_identity(runner_pid, "run_pretraining_study.py", output, proc=proc,
                              expected_start_ticks=runner_start_ticks)
    result = {"schema": 1, "status": "starting", "event": False, "reason": "awaiting_ledger",
              "active_arm": None, "progress": {"step": 0, "planned_steps": 1000, "completed_arms": 0, "total_arms": 6},
              "runner": runner, "launcher": None,
              "activity": {"age_seconds": None, "progress_age_seconds": None, "log": None}}
    ledger_path = output / "study.json"
    ledger = None
    try:
        ledger = read_json(ledger_path)
        arm_list = ledger["arms"]
        result["progress"]["completed_arms"] = sum(arm["status"] == "complete" for arm in arm_list)
        result["progress"]["total_arms"] = len(arm_list)
        result["progress"]["planned_steps"] = ledger["configuration"]["steps"]
        active = next((arm for arm in arm_list if arm["id"] == ledger.get("active_arm")), None)
        result["active_arm"] = active["id"] if active else None
        activity_files, progress_files = [ledger_path], []
        if active:
            arm_output = relative_file(output, active["out"])
            attempt = active["attempts"][-1] if active.get("attempts") else {}
            result["launcher"] = process_identity(attempt.get("launcher_pid"), "train_distributed.py", arm_output, proc=proc)
            if attempt.get("log"):
                log = relative_file(output, attempt["log"])
                result["activity"]["log"] = str(log.relative_to(output.resolve()))
                activity_files.append(log)
            run_path, metrics_path = arm_output / "run.json", arm_output / "metrics.jsonl"
            progress_files.extend((run_path, metrics_path))
            activity_files.extend(progress_files)
            result["progress"]["step"] = latest_metric(metrics_path)
            try:
                result["progress"]["step"] = max(result["progress"]["step"], int(read_json(run_path).get("completed_steps", 0)))
            except (OSError, ValueError, TypeError):
                pass
        newest = newest_mtime(activity_files)
        progress = newest_mtime(progress_files)
        result["activity"]["age_seconds"] = max(0, round(now - newest, 1)) if newest is not None else None
        result["activity"]["progress_age_seconds"] = max(0, round(now - progress, 1)) if progress is not None else None
        if ledger.get("status") in ("complete", "failed", "interrupted"):
            result.update(status=ledger["status"], event=True, reason="study_" + ledger["status"])
            if ledger["status"] == "complete":
                result["progress"]["step"] = result["progress"]["planned_steps"]
        else:
            result.update(status="running", reason="study_active")
    except FileNotFoundError:
        pass
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        result.update(status="failed", event=True, reason="invalid_study_ledger")
    if not result["event"]:
        if not runner["alive"] or not runner["argv_match"]:
            result.update(status="failed", event=True, reason="runner_missing_or_replaced")
        elif ledger is None:
            try:
                uptime = float((proc / "uptime").read_text().split()[0])
                age = uptime - runner["start_ticks"] / os.sysconf("SC_CLK_TCK")
                if age > startup_grace_seconds:
                    result.update(status="stalled", event=True, reason="ledger_startup_timeout")
            except (OSError, ValueError, TypeError):
                result.update(status="failed", event=True, reason="cannot_verify_startup_age")
        else:
            launcher = result["launcher"]
            age = result["activity"]["age_seconds"]
            progress_age = result["activity"]["progress_age_seconds"]
            if launcher is not None and (not launcher["alive"] or not launcher["argv_match"]) and age is not None and age > 15:
                result.update(status="failed", event=True, reason="launcher_missing_or_replaced")
            elif (progress_age if progress_age is not None else age or 0) > stall_seconds:
                result.update(status="stalled", event=True, reason="no_training_progress")
    identity = {"status": result["status"], "reason": result["reason"], "active_arm": result["active_arm"],
                "step": result["progress"]["step"], "runner_pid": runner_pid,
                "runner_start_ticks": runner_start_ticks or runner["start_ticks"]}
    result["event_fingerprint"] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--runner-pid", required=True, type=int)
    parser.add_argument("--runner-start-ticks", type=int)
    parser.add_argument("--stall-seconds", type=float, default=600)
    parser.add_argument("--startup-grace-seconds", type=float, default=120)
    parser.add_argument("--integrity", action="store_true", help="also audit frozen source and recorded training evidence")
    args = parser.parse_args(argv)
    result = inspect_study(args.out.resolve(), args.runner_pid, runner_start_ticks=args.runner_start_ticks,
                           stall_seconds=args.stall_seconds, startup_grace_seconds=args.startup_grace_seconds)
    if args.integrity and (args.out / "study.json").exists():
        try:
            issues = integrity_issues(args.out.resolve())
        except (OSError, ValueError, KeyError, TypeError) as error:
            issues = ["integrity_check_failed:" + type(error).__name__]
        result["integrity"] = {"checked": True, "issues": issues}
        if issues:
            result.update(status="failed", event=True, reason="independent_integrity_check")
            result["event_fingerprint"] = hashlib.sha256(json.dumps(issues).encode()).hexdigest()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
