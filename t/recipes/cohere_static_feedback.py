"""Compare one static-feedback repair with one fresh internal teacher sample.

Sources: spec_repair.repair_question, spec_first.kept_specifications,
v9_strict_specs, cohere_json_audit, https://docs.cohere.com/reference/chat,
https://arxiv.org/abs/2410.15756. No product runtime calls this module.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "t"))

import cohere_proxy as proxy
import cohere_task_json_v2 as codec
from v6_server_route import Decoder, canonical

MODEL = "command-a-03-2025"
STAGE = 40100
MAX_NEW = 8000
ARMS = ("fresh", "feedback")
FEEDBACK = (
    "\n\nA previous JSON candidate was rejected by the static contract checker.\n"
    "Previous candidate:\n```json\n{attempt}\n```\n\n"
    "Exact checker diagnostic:\n{diagnostic}\n\n"
    "Correct the candidate using this diagnostic. Preserve the original problem's meaning, "
    "parameter order and result type. Keep the task body empty. Do not drop requirements or "
    "replace a meaningful condition with true merely to pass the checker. "
    "Return the complete corrected JSON contract using the required schema."
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def validate_case(case):
    record = case["record"]
    body = record["request"]
    key = hashlib.sha256(canonical([record["identity"], body])).hexdigest()
    if case["source_cache"] != key + ".json":
        raise ValueError("source request does not match its cache identity")
    source = record["response"]["cohere_source"]
    if (body["model"] != MODEL or source["representation"] != "json-v2"
            or source["identity"] != codec.identity()
            or not record["identity"].endswith(":" + codec.identity())):
        raise ValueError("source model or transport changed")
    if source["request"] != proxy.to_cohere(body, MODEL, 0, "json-v2"):
        raise ValueError("source wire request changed")
    conversion = source["conversion"]
    if (source["response"].get("finish_reason") != "COMPLETE"
            or conversion.get("status") != "refused"
            or not conversion.get("reason", "").startswith("ill-formed contract:")):
        raise ValueError("a complete static-contract refusal is required")
    replay = proxy.structured_reply(source["response"], source["request"], body["max_tokens"], MODEL, "json-v2")
    if record["response"] != replay:
        raise ValueError("source diagnostic or preserved response no longer reproduces")


def conversations(case):
    validate_case(case)
    source = case["record"]["response"]["cohere_source"]
    attempt = "".join(b["text"] for b in source["response"]["message"]["content"] if b["type"] == "text")
    fresh = deepcopy(case["record"]["request"]["messages"])
    feedback = deepcopy(fresh)
    feedback[1]["content"] += FEEDBACK.format(attempt=attempt, diagnostic=source["conversion"]["reason"])
    return {"fresh": fresh, "feedback": feedback}


def request_body(messages):
    # Same request and seed construction as Decoder.one; verified against that driver in tests.
    seed = int(hashlib.sha256(canonical([STAGE, messages])).hexdigest()[:8], 16) & 0x7fffffff
    return {"model": MODEL, "messages": messages, "max_tokens": MAX_NEW,
            "temperature": 0.7, "top_p": 0.95, "top_k": 0, "min_p": 0,
            "repeat_penalty": 1.0, "seed": seed, "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}}


def check_membership(selection, pool, allowed):
    import spec_first_rows

    cases = selection["cases"]
    ids = [case["task_id"] for case in cases]
    if not ids or len(ids) != len(set(ids)) or len(ids) > 50:
        raise ValueError("the selected panel must be nonempty, unique and bounded")
    if any(type(tid) is not int or tid not in allowed or tid not in pool for tid in ids):
        raise ValueError("a selected problem is not on the training side")
    for case in cases:
        entry = pool[case["task_id"]]
        expected = spec_first_rows.spec_question(entry, entry["rec"]["code"].strip("\n"))[1]
        if case["record"]["request"]["messages"][1] != expected:
            raise ValueError("source prompt does not belong to its declared problem")


def source_hashes():
    paths = set((ROOT / "t").glob("*.py")) | set((ROOT / "t/verifiers").rglob("*.py"))
    paths |= set((ROOT / "nl/data").glob("*.gz"))
    paths |= {ROOT / "t/recipes" / name for name in (
        "cohere_static_feedback.py", "cohere_proxy.py", "cohere_task_json.py", "cohere_task_json_v2.py",
        "cohere_json_audit.py", "v6_server_route.py", "v9_strict_specs.py", "requirements-cohere-json.txt")}
    workflow = ROOT / ".github/workflows/cohere-static-feedback.yml"
    if workflow.exists():
        paths.add(workflow)
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


def plan(selection, tag):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", tag):
        raise ValueError("use a simple measurement tag")
    import graded_pool
    import spec_experiment as se

    pool = se.pool("v5")
    allowed = graded_pool.training_ids(ROOT / "t/out/loop/split-v5.json", pool)
    check_membership(selection, pool, allowed)
    requests, order = [], []
    for index, case in enumerate(selection["cases"]):
        questions = conversations(case)
        for arm in ARMS if index % 2 == 0 else ARMS[::-1]:
            requests.append(request_body(questions[arm]))
            order.append({"case_index": index, "task_id": case["task_id"], "arm": arm})
    panel = "".join(str(c["task_id"]) + "\n" for c in selection["cases"])
    identity = "teacher-cohere:" + MODEL + ":static-feedback:" + tag + ":" + codec.identity()
    return {"identity": identity, "model": MODEL, "tag": tag, "representation": "json-v2", "think": 0,
            "codec_identity": codec.identity(), "prices_per_million": list(proxy.PRICE[MODEL]),
            "panel_sha256": hashlib.sha256(panel.encode()).hexdigest(),
            "route_args": ["static-feedback", "--stage", str(STAGE), "--one-per-arm"],
            "driver_sha256": digest(Path(__file__)), "sources": source_hashes(),
            "selection_canonical_sha256": hashlib.sha256(canonical(selection)).hexdigest(),
            "requests": requests, "request_order": order}


def generate(expected, endpoint, cache):
    if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]+/v1/chat/completions", endpoint):
        raise ValueError("use the local internal teacher proxy")
    cache.mkdir(parents=True, exist_ok=True)
    protocol = {k: expected[k] for k in (
        "identity", "model", "panel_sha256", "route_args", "driver_sha256", "sources")}
    path = cache / "protocol.json"
    if path.exists() and json.loads(path.read_text()) != protocol:
        raise ValueError("registered generation procedure changed")
    atomic_json(path, protocol)
    decoder = Decoder(endpoint, MODEL, expected["identity"], cache, concurrency=8)
    decoder.decode(None, None, [r["messages"] for r in expected["requests"]], MAX_NEW, 0.7, 0.95, STAGE)
    for body in expected["requests"]:
        key = hashlib.sha256(canonical([expected["identity"], body])).hexdigest()
        record = json.loads((cache / (key + ".json")).read_text())
        if record["request"] != body or record["identity"] != expected["identity"]:
            raise ValueError("saved request differs from the registration")
    atomic_json(cache / "completed.json", protocol)


def score(selection, expected, cache, out):
    import spec_check
    import spec_experiment as se
    import spec_first

    pool = se.pool("v5")
    rows = {arm: [{"task_id": c["task_id"], "tasks": [], "sources": [], "scores": []}
                  for c in selection["cases"]] for arm in ARMS}
    diagnostics = []
    for body, item in zip(expected["requests"], expected["request_order"]):
        key = hashlib.sha256(canonical([expected["identity"], body])).hexdigest()
        response = json.loads((cache / (key + ".json")).read_text())["response"]
        source = response.get("cohere_source", {})
        detail = {**item, "request_key": key, "conversion": source.get("conversion"),
                  "error": response.get("error"), "kept_before_strict": False}
        if source.get("conversion", {}).get("status") == "accepted":
            text = "".join(b["text"] for b in source["response"]["message"]["content"] if b["type"] == "text")
            task = codec.decode_contract(text)
            kept, counts = spec_first.kept_specifications([(item["arm"] + ":" + key, task)], pool[item["task_id"]], 1)
            detail["visible_gate"] = counts
            if kept:
                try:
                    reference = spec_check.check_task(kept[0]["task"], pool[item["task_id"]], 100,
                                                      random.Random(100000 + item["case_index"]))
                except Exception as error:
                    reference = {"status": "check raised: " + type(error).__name__}
                detail["reference_prefilter"] = reference
                if spec_first.reference_keeps(reference):
                    row = rows[item["arm"]][item["case_index"]]
                    row.update(tasks=[kept[0]["task"]], sources=[kept[0]["source"]], scores=[kept[0]["scores"]])
                    detail["kept_before_strict"] = True
        diagnostics.append(detail)
    atomic_json(out / "diagnostics.json", diagnostics)
    for arm in ARMS:
        path = out / (arm + "-prestrict.jsonl")
        path.write_text("".join(json.dumps(row) + "\n" for row in rows[arm]))
        # Empty rows preserve the selected-case index, and hence matched strict-check seeds.
        subprocess.run([sys.executable, str(ROOT / "t/recipes/v9_strict_specs.py"), "--kept", str(path),
                        "--pool", "v5", "--draws", "1000", "--floor", "0.9", "--jobs", "4",
                        "--out", str(out / (arm + "-strict-kept.jsonl")),
                        "--report", str(out / (arm + "-strict.json")),
                        "--dropped", str(out / (arm + "-strict-dropped.jsonl"))], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "generate", "score"))
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--selection-sha256", required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8854/v1/chat/completions")
    args = parser.parse_args()
    if digest(args.selection) != args.selection_sha256:
        raise ValueError("selection differs from its registered bytes")
    selection = json.loads(args.selection.read_text())
    expected = plan(selection, args.tag)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.mode == "plan":
        if args.expected.exists() and json.loads(args.expected.read_text()) != expected:
            raise ValueError("refusing to overwrite a different registration")
        atomic_json(args.expected, expected)
        print(json.dumps({"problems": len(selection["cases"]), "logical_requests": len(expected["requests"]),
                          "expected_sha256": digest(args.expected)}))
        return 0
    if json.loads(args.expected.read_text()) != expected:
        raise ValueError("current source or expected requests differ from the registration")
    import py_sandbox
    if py_sandbox.backend() != "bwrap" or not py_sandbox.available():
        raise ValueError("the registered bubblewrap sandbox must work before this run")
    cache = args.out / "cache"
    if args.mode == "generate":
        import fcntl
        with (args.out / "run.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            generate(expected, args.endpoint, cache)
    else:
        from cohere_json_audit import audit
        checked = audit(cache, args.out / "ledger.jsonl", args.out / "proxy.jsonl", expected)
        atomic_json(args.out / "audit.json", checked)
        score(selection, expected, cache, args.out)
        atomic_json(args.out / "COMPLETE.json", {"expected_sha256": digest(args.expected),
                    "audit_sha256": digest(args.out / "audit.json"),
                    "arm_report_sha256": {a: digest(args.out / (a + "-strict.json")) for a in ARMS}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
