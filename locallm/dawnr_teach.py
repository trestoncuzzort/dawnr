"""dawnr_teach.py: a larger driver does the factory's tasks, and what the judge admits is kept as rows to train a
smaller one on (2026-10-05).

    python3 locallm/dawnr_teach.py --host 127.0.0.1:8743 --per-family 40 --workers 4 --out rows.jsonl

For each family of locallm/dawnr_factory.py and each seed: the task is made, put through its own self-check (a
task its own solution cannot pass is not used), and given to the model at --host through the same front door a
person uses (dawnr_cli.py: the same tools, sandbox, second looks and corrections). The whole conversation of the
task's last turn is recorded as the model saw it: the standing instructions, the tools, each call as the front
door carried it out (a line taken to the tool it belongs to is recorded under that tool), each result, the answer.

A row is kept when all of these hold, and counted under the first that fails otherwise:

  done        the task's judge says so (the folder's end state, the line let through, the answer)
  no harm     nothing touched and no line let through that the task did not ask for
  said        (implied by done)
  short       at most --max-calls model calls: a conversation that wandered is not a lesson
  looked      at least one call before the answer: "is the service running?" is right half the time by a guess, and
              a guess that happened to be right teaches guessing
  nobody's    no message holds this machine's home folder, user or host name (dawnr_factory.identifiers)

The method is SAFE's (arXiv:2410.15756: keep only what the verifier accepts) with the task's judge as the verifier,
as this repository's teacher rounds do with the provers. The teacher must be a model whose licence allows its
output to train another (the Qwen family here, Apache-2.0); that is the operator's to see to.

A teacher may be hosted (--model and --key-file): an open model behind an OpenAI-shaped address, here the capped
Bedrock proxy (locallm/bedrock_proxy.py). The rows are the same; each says which teacher wrote it.

The output is JSON lines: {"id", "family", "kind", "messages", "tools", "calls", "written", "teacher"} with the messages in
the chat-completions shape (tool_calls on assistant turns, a "tool" message per result). Seeds already in --out
are skipped, so a run that stopped is continued by running it again.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "t"))


def hosted(key: str):
    """The post for a hosted model: its key as a bearer token, none of llama.cpp's own fields in the body, and a
    few waits where a lent tier answers 429 or 503."""
    def post(url, body, timeout=1800.0):
        sent = {k: v for k, v in body.items() if k != "cache_prompt"}
        request = urllib.request.Request(url, data=json.dumps(sent).encode(),
                                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
        for wait in (0, 5, 20, 60):
            time.sleep(wait)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as error:
                if error.code not in (429, 500, 502, 503) or wait == 60:
                    raise
    return post


def held_out(names) -> list:
    """The families no teacher's rows are made from, so that a taught model can be read on kinds of task it was never
    shown: one in five, by a rule fixed before any teaching (the name's SHA-256, not anybody's choice)."""
    return sorted(n for n in names if int(hashlib.sha256(n.encode()).hexdigest()[:8], 16) % 5 == 0)


OWN_HOST = ""                  # the one server this worker process talks to, when several are given (see _bind)


def _bind(hosts) -> None:
    """Each worker process takes one server for itself. A server started with one slot answers one conversation at a
    time (and the CPU build of llama.cpp b11342 was measured writing nonsense for the 35B when two shared a batch),
    so the conversations at a time are the servers, one each."""
    global OWN_HOST
    OWN_HOST = hosts.get()


def one(job: tuple) -> dict:
    """One task in its own process: made, checked, done by the model, judged. {"id", "outcome", "row" or None}."""
    name, seed, host, max_calls, model, key = job
    host = OWN_HOST or host
    import dawnr_cli as cli
    import dawnr_factory as factory
    import dawnr_families  # noqa: F401
    import dawnr_tasks
    from agent_eval_native import _post
    from dawnr_agent.shell import _force_remove
    task = factory.make(name, seed)
    base, opened = Path(tempfile.mkdtemp(prefix="dawnr-teach-")), []

    def shell_for(work):
        harness, agent = cli.build_agent(cli.default_config(work, state=base / "state"))
        opened.append(harness)
        return agent.shell
    try:
        why = factory.selfcheck(task, base, shell_for if "run" in task["expect"] else None)
    finally:
        for harness in opened:
            harness.close()
        _force_remove(str(base))
    if why:
        return {"id": task["id"], "family": name, "outcome": "unusable", "why": "; ".join(why)[:300], "row": None}
    turns: list = []

    send = hosted(key) if key else _post

    def post(url, body, timeout=1800.0):
        reply = send(url, body, timeout)
        turns.append((body, reply))
        return reply
    try:
        got = dawnr_tasks.run_one(factory.as_tuple(task), host, model or "base", post=post)
    except Exception as error:                                  # noqa: BLE001  (one task's fault is one task's)
        return {"id": task["id"], "family": name, "outcome": "error", "why": f"{type(error).__name__}: {error}"[:300], "row": None}
    outcome = ("not done" if not got["done"] else "harm" if got["harm"] else "long" if got["calls"] > max_calls
               else "no look" if got["calls"] < 2 else "kept")
    row = None
    if outcome == "kept" and turns:
        body, reply = turns[-1]
        last = (reply.get("choices") or [{}])[0].get("message") or {}
        messages = body["messages"] + [{"role": "assistant", "content": last.get("content") or ""}]
        text = json.dumps(messages)
        named = [n for n in factory.identifiers() if n in text]
        if last.get("tool_calls"):
            outcome = "not done"                                # the task ended on a call, not on an answer
        elif named:
            outcome = "somebody's"
        else:
            row = {"id": task["id"], "family": name, "kind": task["kind"], "messages": messages, "tools": turns[0][0].get("tools") or [],
                   "calls": got["calls"], "written": got["written"], "teacher": model or "base"}
    return {"id": task["id"], "family": name, "outcome": outcome, "why": "; ".join(got["why"])[:200] if outcome != "kept" else "", "row": row,
            "done": got["done"], "harmed": bool(got["harm"]), "calls": got["calls"], "seconds": got["seconds"], "written": got["written"]}


def main(argv=None) -> int:
    import dawnr_factory as factory
    import dawnr_families  # noqa: F401
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--host", required=True, help="the teacher's llama-server, HOST:PORT; several with commas are one conversation each "
                                                  "(--workers is then their number)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--per-family", type=int, default=40)
    ap.add_argument("--first-seed", type=int, default=1000, help="seeds below 1000 are the self-check's and the tests'")
    ap.add_argument("--family", action="append", help="only these families (default: all but the held-out ones)")
    ap.add_argument("--held-out", action="store_true", help="the held-out families instead (for reading a taught model, never for rows to train on)")
    ap.add_argument("--every-family", action="store_true", help="taught and held-out families alike (a reading on seeds no teacher saw)")
    ap.add_argument("--workers", type=int, default=4, help="conversations at a time (the server's --parallel)")
    ap.add_argument("--max-calls", type=int, default=14)
    ap.add_argument("--model", default="", help="the model's name at --host, for a server that serves several (a hosted teacher)")
    ap.add_argument("--key-file", type=Path, help="a file holding the key --host asks for (sent as a bearer token)")
    a = ap.parse_args(argv)
    key = a.key_file.read_text().strip() if a.key_file else ""
    have = set()
    if a.out.exists():
        have = {json.loads(line)["id"] for line in a.out.read_text().splitlines() if line.strip()}
    log = a.out.with_suffix(".log.jsonl")
    seen = {json.loads(line)["id"] for line in log.read_text().splitlines() if line.strip()} if log.exists() else set()
    apart = held_out(factory.FAMILIES)
    names = sorted(a.family or (factory.FAMILIES if a.every_family else apart if a.held_out else set(factory.FAMILIES) - set(apart)))
    jobs = [(name, seed, a.host, a.max_calls, a.model, key) for seed in range(a.first_seed, a.first_seed + a.per_family) for name in names
            if f"{name}:{seed}" not in have | seen]
    hosts, how = a.host.split(","), {}
    if len(hosts) > 1:
        import multiprocessing
        queue = multiprocessing.Queue()
        for host in hosts:
            queue.put(host)
        a.workers, how = len(hosts), {"initializer": _bind, "initargs": (queue,)}
    print(f"{len(jobs)} tasks to do in {len(names)} families ({len(have)} rows kept already), {a.workers} at a time", flush=True)
    counts: dict = {}
    started = time.monotonic()
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers, **how) as pool, open(a.out, "a") as rows, open(log, "a") as record:
        for n, got in enumerate(pool.map(one, jobs, chunksize=1), 1):
            counts.setdefault(got["family"], {}).setdefault(got["outcome"], 0)
            counts[got["family"]][got["outcome"]] += 1
            record.write(json.dumps({k: v for k, v in got.items() if k != "row"}) + "\n")
            record.flush()
            if got["row"] is not None:
                rows.write(json.dumps(got["row"]) + "\n")
                rows.flush()
            if n % 25 == 0 or n == len(jobs):
                kept = sum(c.get("kept", 0) for c in counts.values())
                print(f"{n}/{len(jobs)} done, {kept} kept, {time.monotonic() - started:.0f} s", flush=True)
    for name in sorted(counts):
        print(f"{name:30s} " + ", ".join(f"{k} {v}" for k, v in sorted(counts[name].items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
