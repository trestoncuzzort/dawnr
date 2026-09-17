#!/usr/bin/env python3
"""t/run_everything.py -- run the rest of the RTX 4080 data run without waiting for a person (2026-09-17).

Uses the steps of t/lab.py's Collect data tab (same commands, same logs, same pid files, so t lab shows
every step running) and chains them:

  1. wait for answer writing to finish (start it if it is not running)
  2. two chains at once, so neither machine waits:
     GPU (this machine): Phi-4-mini answers; Ollama: repairs of every seed, the HumanEval problems, a second
       generator; the small base answers; a repair round on the new answer sets
     lab workstation: the seeds, then each new answer set as soon as it is written, then Phi's and the base
       model's held-out answers
  3. clean pool over split-v4, train the student, student answers, locallm model
  4. held-out grading for the rest, then the score

A failed step is retried once; if it fails again, run_everything writes why to NOTES-home.md, sends a desktop
notification and carries on with what does not depend on it. Run it from the repository root:

    python3 t/run_everything.py
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TUP = HERE.parent
sys.path.insert(0, str(HERE))
from lab import EVENTS, KERNEL_PATH, RUNS, STEPS   # noqa: E402

STEP = {s[0]: s for s in STEPS}
LOGS = RUNS / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
ENV = dict(os.environ, PATH=KERNEL_PATH + os.pathsep + os.environ.get("PATH", ""), T_WATCH=str(EVENTS))
failed: list[str] = []


def note(line: str):
    with open(RUNS / "NOTES-home.md", "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} run_everything: {line}\n")
    print(line, flush=True)


def notify(text: str):
    subprocess.run(["notify-send", "-a", "t lab", "t lab", text], capture_output=True,
                   env=dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":0")))


def done(key: str) -> bool:
    return subprocess.run(["bash", "-lc", STEP[key][4]], cwd=TUP, env=ENV, capture_output=True).returncode == 0


def pid_of(key: str) -> int | None:
    try:
        pid = int((LOGS / f"{key}.pid").read_text().split()[0])
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError, IndexError):
        return None


def wait_idle(key: str):
    while pid_of(key):
        time.sleep(20)


def run(key: str, env_extra: dict | None = None, need_done: bool = True, retries: int = 1) -> bool:
    """Run one step the way t lab does (log, pid file, notes); True when it succeeded."""
    wait_idle(key)
    if need_done and done(key):
        return True
    _key, title, _what, cmd, _check, _uses = STEP[key]
    for attempt in range(retries + 1):
        with open(LOGS / f"{key}.log", "a") as out:
            out.write(f"\n### {time.strftime('%Y-%m-%d %H:%M:%S')} {cmd} (run_everything, attempt {attempt + 1})\n")
            out.flush()
            note(f"start `{key}` ({title}), attempt {attempt + 1}")
            p = subprocess.Popen(["bash", "-lc", cmd], cwd=TUP, stdout=out, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, env=dict(ENV, **(env_extra or {})), start_new_session=True)
            (LOGS / f"{key}.pid").write_text(f"{p.pid} {time.time()}")
            rc = p.wait()
        ok = rc == 0 and (done(key) if need_done else True)
        note(f"end `{key}`: exit {rc}, {'ok' if ok else 'not done'}")
        if ok:
            return True
    failed.append(key)
    note(f"`{key}` failed twice; see logs/{key}.log")
    notify(f"{title} failed twice. The rest carries on where it can.")
    return False


def stop_ollama():
    pid = pid_of("ollama-serve")
    running = bool(pid) or subprocess.run(["pgrep", "-f", "^ollama serve"], capture_output=True).returncode == 0
    if pid:
        os.killpg(pid, signal.SIGTERM)
    subprocess.run(["pkill", "-f", "^ollama serve"], capture_output=True)
    if running:
        note("Ollama stopped: the GPU goes to the next step")
        time.sleep(10)


def grading():
    """Seeds on the lab workstation and here at once, until every seed has kernels.md."""
    for _round in range(2):
        wait_idle("grade")                      # a lab job started by hand finishes first
        # the lab workstation only: grading here beside a GPU step ran this machine out of memory (2026-09-17 07:32,
        # the OOM killer took run_everything, Phi-4-mini's generation and the local run_par together)
        threads = [threading.Thread(target=run, args=("grade",), kwargs={"need_done": False, "retries": 0})]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if done("grade"):
            return True
        # a killed run leaves its claim behind; with no grader running, every claim is stale
        for claim in (TUP / "t/out/spec-experiment").glob("*/.grading"):
            claim.rmdir()
            note(f"removed stale claim {claim.parent.name}/.grading")
    failed.append("grade")
    note("grading did not finish every seed after two rounds")
    notify("Grading did not finish every seed. See NOTES-home.md.")
    return False


def start_ollama() -> bool:
    if not done("ollama-serve"):
        threading.Thread(target=run, args=("ollama-serve",), kwargs={"need_done": False, "retries": 0},
                         daemon=True).start()
        for _ in range(60):
            if done("ollama-serve"):
                break
            time.sleep(5)
    return done("ollama-serve")


def wait_done(key: str, poll: int = 60) -> bool:
    """Wait until another thread's step is done, or has stopped for good."""
    while not done(key):
        if key in failed:
            return False
        time.sleep(poll)
    return True


def gpu_chain():
    """Everything that needs the 4080, one at a time, ordered so the lab workstation always has work."""
    notify("Phi-4-mini is starting: its answers to the 232 held-out problems, in bf16.")
    note("Phi-4-mini answers starting (the model to beat)")
    if run("phi"):
        notify("Phi-4-mini answers are written. Growing the pool next.")
    if start_ollama():
        run("repair")                       # the lab grades these while new answers are written
        run("more-problems")
    else:
        failed.append("ollama-serve")
        note("Ollama did not start; repairs and new answers skipped")
    stop_ollama()
    run("base")                             # while the lab grades the new answers
    if wait_done("grade-growth") and start_ollama():
        run("repair-growth")
    stop_ollama()


def lab_chain():
    """Everything the lab workstation grades, each set as soon as the GPU has written it."""
    grading()
    for source, grade in (("repair", "grade-repair"), ("more-problems", "grade-growth"),
                          ("repair-growth", "grade-growth-repair")):
        if wait_done(source):
            run(grade)
    run("grade-heldout", need_done=False)   # Phi's and the base model's, while training runs


def main() -> int:
    note("started (growth plan: repairs, HumanEval problems, a second generator)")
    wait_idle("generate")
    if not done("generate"):
        start_ollama()
        if not run("generate"):
            notify("Answer writing failed twice; run_everything stopped.")
            return 1
    stop_ollama()

    g = threading.Thread(target=gpu_chain)
    l = threading.Thread(target=lab_chain)
    g.start()
    l.start()
    g.join()
    l.join()

    if run("pool"):
        if run("train"):
            run("student")
        run("locallm")
    run("grade-heldout")
    run("score")
    note("finished" + (f"; failed: {', '.join(failed)}" if failed else ""))
    notify("Data run finished: t/out/score-r4.md" if done("score") else "Data run stopped; see NOTES-home.md")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
