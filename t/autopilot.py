#!/usr/bin/env python3
"""t/autopilot.py -- a small local model presses t lab's buttons while nobody is watching (2026-09-17).

    python3 t/autopilot.py [--model qwen2.5:3b] [--every 180] [--once] [--dry-run]

Every cycle it reads the same state t lab shows (t/steps.json's steps, each one's done test, whether it is
running, its last log lines) plus the machine (memory, the graphics card, Ollama, the lab workstation over SSH),
works out which actions are LEGAL right now, and asks a local model served by Ollama to choose one. The model
only ever picks from that list: the list is built here, in code, from the preconditions, so a wrong answer can
pick a pointless action but never an unsafe one. With no Ollama, a bad reply or an unknown action, the first
candidate by priority is taken instead and the log says so.

What it may do: run a step whose resource is free, start or stop Ollama, clear a stale grading claim, fetch a
table the lab workstation wrote, open the the VPN window, restart the orchestrator, wait, or raise an alert.
What it may not do, by construction: run a step twice, run two steps that want the same resource, touch git,
delete data, or change anything about the experiment (pools, prompts, splits, thresholds).

An alert appends to t/runs/<date>/ALERTS.md, sends a desktop notification and, when the same step has failed
twice, stops trying that step. ALERTS.md is what to read first when coming back to the machine, and what to
hand to Claude: every entry carries the step, the verdict, the last log lines and the model's reading of them.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lab import EVENTS, KERNEL_PATH, RUNS, SPEC_EXP, STEPS, TUP   # noqa: E402

LOGS = RUNS / "logs"
ALERTS = RUNS / "ALERTS.md"
OPLOG = LOGS / "autopilot.log"
ENV = dict(os.environ, PATH=KERNEL_PATH + os.pathsep + os.environ.get("PATH", ""), T_WATCH=str(EVENTS))
LAB = os.environ.get("T_LAB", "tmcuzzort@the-lab-workstation")
MAX_ATTEMPTS = 2            # per step, per run of the operator
MAX_RESTARTS = 3            # orchestrator restarts per hour


def sh(cmd: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-lc", cmd], cwd=TUP, env=ENV, capture_output=True, text=True, timeout=timeout)


def log(line: str):
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(OPLOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    print(line, flush=True)


def notify(text: str):
    subprocess.run(["notify-send", "-a", "t lab autopilot", "t lab", text], capture_output=True,
                   env=dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":0")))


def alert(step: str, why: str, reading: str = ""):
    ALERTS.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERTS, "a") as f:
        f.write(f"\n## {time.strftime('%Y-%m-%d %H:%M')} {step}\n\n{why}\n")
        if reading:
            f.write(f"\nThe local model's reading:\n\n{reading}\n")
        tail = tail_log(step, 25)
        if tail:
            f.write(f"\nLast lines of logs/{step}.log:\n\n```\n{tail}\n```\n")
    log(f"ALERT {step}: {why}")
    notify(f"{step}: {why[:120]}")


def tail_log(key: str, n: int = 8) -> str:
    try:
        lines = [l for l in (LOGS / f"{key}.log").read_text(errors="replace").splitlines() if l.strip()]
        return "\n".join(lines[-n:])
    except OSError:
        return ""


def pid_of(key: str) -> int | None:
    try:
        pid = int((LOGS / f"{key}.pid").read_text().split()[0])
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError, IndexError):
        return None


def done(key: str, check: str) -> bool:
    try:
        return sh(check, timeout=120).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def machine() -> dict:
    free = sh("free -m | awk 'NR==2{print $7}'").stdout.strip()
    gpu = sh("nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader").stdout.strip()
    ollama = sh("curl -sf http://127.0.0.1:11434/ >/dev/null && echo up || echo down").stdout.strip()
    lab = sh(f"timeout 15 ssh -o BatchMode=yes -o ConnectTimeout=10 {LAB} true && echo up || echo down").stdout.strip()
    orch = sh("systemctl --user is-active t-run-all").stdout.strip()
    hand = sh("systemctl --user is-active t-handover").stdout.strip()
    try:
        last_ev = time.time() - EVENTS.stat().st_mtime
    except OSError:
        last_ev = -1
    return {"free_mb": free, "gpu": gpu, "ollama": ollama, "lab": lab, "orchestrator": orch,
            "handover": hand, "last_check_seconds_ago": int(last_ev)}


def state() -> tuple[dict, list[dict]]:
    m = machine()
    steps = []
    for key, title, _what, _cmd, check, uses in STEPS:
        running = pid_of(key) is not None
        steps.append({"step": key, "title": title, "uses": uses or "anything", "running": running,
                      "done": (False if running else done(key, check)), "last_log": tail_log(key, 4)})
    return m, steps


def candidates(m: dict, steps: list[dict], attempts: dict) -> list[dict]:
    """Every action that is legal right now, most useful first. The model chooses from this and nothing else."""
    out = []
    busy = {s["uses"] for s in steps if s["running"]}
    if m["orchestrator"] == "active" or m["handover"] == "active":
        out.append({"action": "wait", "why": "the orchestrator is driving the run"})
        return out
    if m["lab"] == "down":
        out.append({"action": "vpn-connect", "why": "the lab workstation is unreachable, so no grading can run"})
    stale = [p for p in SPEC_EXP.glob("*/.grading") if not any(s["running"] for s in steps if "grade" in s["step"])]
    if stale:
        out.append({"action": "clear-claims", "why": f"{len(stale)} answer set(s) marked as being graded with no grader running"})
    for s in steps:
        if s["done"] or s["running"] or attempts.get(s["step"], 0) >= MAX_ATTEMPTS:
            continue
        need = s["uses"]
        if need in busy or (need == "gpu" and "gpu" in busy):
            continue
        if need == "lab" and m["lab"] != "up":
            continue
        if s["step"] in ("repair", "repair-growth", "more-problems", "generate") and m["ollama"] != "up":
            out.append({"action": "start-ollama", "why": f"{s['step']} needs Ollama and it is down"})
            continue
        if need == "gpu" and s["step"] in ("phi", "base", "train", "student", "locallm") and m["ollama"] == "up":
            out.append({"action": "stop-ollama", "why": f"{s['step']} needs the whole graphics card"})
            continue
        out.append({"action": f"run:{s['step']}", "why": f"{s['title']} is not done and its resource is free"})
    out.append({"action": "wait", "why": "nothing needs doing"})
    seen, uniq = set(), []
    for c in out:
        if c["action"] not in seen:
            seen.add(c["action"])
            uniq.append(c)
    return uniq


def ask_model(model: str, m: dict, steps: list[dict], cands: list[dict]) -> tuple[str, str]:
    """The local model's choice, or ("", "") when it cannot be asked or answers badly."""
    sys_msg = ("You keep a data pipeline running on one machine. You are given the machine's state, the steps and "
               "the actions that are legal right now. Choose exactly one action from the list, the one that makes "
               "the run finish soonest without wasting the graphics card or the shared workstation. Answer with "
               "one JSON object only: {\"action\": \"<one action string from the list>\", \"why\": \"<one short "
               "sentence>\"}. Never invent an action.")
    user = json.dumps({"machine": m, "steps": steps, "legal_actions": [c["action"] for c in cands],
                       "notes": [c["why"] for c in cands]}, indent=1)[:12000]
    body = {"model": model, "stream": False, "format": "json", "keep_alive": "30s",
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 200},
            "messages": [{"role": "system", "content": sys_msg}, {"role": "user", "content": user}]}
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            reply = json.loads(resp.read().decode())["message"]["content"]
        pick = json.loads(reply)
        action = str(pick.get("action", "")).strip()
        if action in {c["action"] for c in cands}:
            return action, str(pick.get("why", ""))[:200]
        log(f"model chose {action!r}, which is not legal; falling back")
    except (OSError, urllib.error.URLError, ValueError, KeyError) as e:
        log(f"model not asked ({type(e).__name__}); falling back to the first candidate")
    return "", ""


def read_failure(model: str, step: str) -> str:
    """A plain-language reading of a failing step's log, for ALERTS.md. Never a command to run."""
    body = {"model": model, "stream": False, "keep_alive": "30s",
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 300},
            "messages": [{"role": "system", "content":
                          "You read one failing log from a data pipeline. In at most four sentences: what failed, "
                          "the most likely cause, and what a person should check. No commands, no guessing at "
                          "numbers."},
                         {"role": "user", "content": f"Step {step} failed twice. Last lines:\n\n{tail_log(step, 40)}"}]}
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode())["message"]["content"].strip()[:1200]
    except (OSError, urllib.error.URLError, ValueError, KeyError):
        return ""


def start_step(key: str, dry: bool) -> subprocess.Popen | None:
    cmd = next(s[3] for s in STEPS if s[0] == key)
    if dry:
        log(f"[dry run] would start {key}: {cmd[:120]}")
        return None
    LOGS.mkdir(parents=True, exist_ok=True)
    out = open(LOGS / f"{key}.log", "a")
    out.write(f"\n### {time.strftime('%Y-%m-%d %H:%M:%S')} {cmd} (autopilot)\n")
    out.flush()
    p = subprocess.Popen(["bash", "-lc", cmd], cwd=TUP, stdout=out, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, env=ENV, start_new_session=True)
    (LOGS / f"{key}.pid").write_text(f"{p.pid} {time.time()}")
    with open(RUNS / "NOTES-home.md", "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} autopilot: started `{key}`\n")
    return p


def act(action: str, why: str, model: str, dry: bool, attempts: dict, restarts: list) -> None:
    log(f"action {action} ({why})")
    if action == "wait":
        return
    if action.startswith("run:"):
        key = action.split(":", 1)[1]
        attempts[key] = attempts.get(key, 0) + 1
        start_step(key, dry)
        return
    if action == "start-ollama":
        if not dry:
            start_step("ollama-serve", dry)
            for _ in range(24):
                time.sleep(5)
                if sh("curl -sf http://127.0.0.1:11434/ >/dev/null").returncode == 0:
                    return
            alert("ollama-serve", "Ollama did not answer within two minutes of being started")
        return
    if action == "stop-ollama":
        if not dry:
            pid = pid_of("ollama-serve")
            if pid:
                os.killpg(pid, signal.SIGTERM)
            sh("pkill -f '^ollama serve'")
            time.sleep(10)
        return
    if action == "clear-claims":
        for claim in SPEC_EXP.glob("*/.grading"):
            if not dry:
                claim.rmdir()
            log(f"cleared claim {claim.parent.name}/.grading")
        return
    if action == "vpn-connect":
        if not dry:
            sh("pgrep -x openconnect >/dev/null || setsid ptyxis --new-window -T 'the VPN' -x "
               "$HOME/.local/bin/vpn-connect >/dev/null 2>&1 &")
            alert("vpn", "The lab workstation is unreachable. The the VPN window is open and needs your sign-in "
                         "and Duo approval; grading waits until then.")
        return
    if action == "restart-orchestrator":
        now = time.time()
        restarts[:] = [t for t in restarts if now - t < 3600]
        if len(restarts) >= MAX_RESTARTS:
            alert("run-all", f"the orchestrator has been restarted {MAX_RESTARTS} times in an hour; not again")
            return
        restarts.append(now)
        if not dry:
            sh("systemctl --user reset-failed t-run-all; systemd-run --user --unit=t-run-all "
               f"--working-directory={TUP} -p StandardOutput=append:{LOGS}/run-all.log "
               f"-p StandardError=append:{LOGS}/run-all.log --setenv=HOME=$HOME --setenv=DISPLAY=:0 "
               "/usr/bin/python3 t/run_everything.py")
        return
    log(f"unknown action {action}, nothing done")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", default="qwen2.5:3b", help="an Ollama model small enough to share the card")
    ap.add_argument("--every", type=int, default=180)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    attempts: dict[str, int] = {}
    restarts: list[float] = []
    reported: set[str] = set()
    log(f"autopilot started (model {a.model}, every {a.every} s{', dry run' if a.dry_run else ''})")
    while True:
        m, steps = state()
        for s in steps:
            key = s["step"]
            if attempts.get(key, 0) >= MAX_ATTEMPTS and not s["done"] and key not in reported:
                reported.add(key)
                alert(key, f"{s['title']} failed {MAX_ATTEMPTS} times; the autopilot will not try it again",
                      read_failure(a.model, key))
        cands = candidates(m, steps, attempts)
        action, why = ask_model(a.model, m, steps, cands) if m["ollama"] == "up" else ("", "")
        if not action:
            action, why = cands[0]["action"], cands[0]["why"] + " (chosen by the rules, not the model)"
        act(action, why, a.model, a.dry_run, attempts, restarts)
        if a.once:
            return 0
        time.sleep(a.every)


if __name__ == "__main__":
    raise SystemExit(main())
