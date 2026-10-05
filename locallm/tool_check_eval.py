"""tool_check_eval.py: how often a call that should have been a question is released, with the model alone and
with locallm/tool_check.py between the model and the tool (2026-10-05).

    python3 locallm/tool_check_eval.py run --host H:P[,H:P ...] --data when2call_test_mcq.jsonl --out answers.jsonl
                                           [--part dev|test] [--n 300]
    python3 locallm/tool_check_eval.py report --answers answers.jsonl [--json r.json] [--any-enum] [--show 5]

When2Call's test set (Ross, Mahabaleshwarkar and Suhara, arXiv:2504.18851; github.com/NVIDIA/When2Call, CC BY 4.0,
kept out of this repository): 3,652 requests built from BFCL v2 Live, each with the tools offered and the right
kind of reply. `tool_call`: a tool fits and the request gives every required value. `request_for_info`: one
required value was removed from the request (`held_out_param`), so the right reply asks for it. `cannot_answer`:
the tool that fits was taken away.

The model is asked once an item, with the tools offered natively (llama-server's OpenAI `tools`), temperature 0.
Its reply is stored with the request and the tools, so the check can be rerun without the model. Two readings of
the same replies:

  native    what the model emitted: a call is released whenever it wrote one
  checked   tool_check.check_all over the calls it wrote: released, or turned into a question naming the
            parameter, or refused

Counted without a judge: of each kind of item, how many have a call released; for `tool_call` items whether the
released call names the benchmark's tool and whether its arguments agree with the benchmark's reference call
(`same`: text compared without case or accents, a list in the reference read as alternatives, as BFCL writes its
possible answers); for `request_for_info` items whether the question the check asks names the removed parameter.
What the model says when it writes no call is not classified: that needs a reader, and no model is the judge here.

The items are split once, by a fixed seed: `dev` (100 of each kind) is where the rule was looked at; `test` is
the rest, of which `--n` of each kind are drawn. Registered in locallm/PREDICT-2026-10-05-tool-check.md.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
import threading
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallm import rag_rgb, tool_check as tc  # noqa: E402

SEED = 2026
KINDS = ("tool_call", "request_for_info", "cannot_answer")
DEV = 100
TYPES = {"dict": "object", "object": "object", "float": "number", "number": "number", "double": "number",
         "integer": "integer", "int": "integer", "long": "integer", "string": "string", "str": "string",
         "boolean": "boolean", "bool": "boolean", "array": "array", "list": "array", "tuple": "array", "null": "null"}


def safe(name: str) -> str:
    """A tool's name as OpenAI's shape allows it (BFCL's own handlers replace the dot the same way)."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)[:64]


def schema(s):
    """A BFCL parameter schema as JSON Schema: its types renamed (`dict` is `object`), unknown ones dropped."""
    if isinstance(s, list):
        return [schema(x) for x in s]
    if not isinstance(s, dict):
        return s
    out = {}
    for k, v in s.items():
        if k == "type" and isinstance(v, str):
            if v.lower() in TYPES:
                out["type"] = TYPES[v.lower()]
        elif k == "properties" and isinstance(v, dict):
            out[k] = {name: schema(p) for name, p in v.items()}
        elif k in ("items", "additionalProperties"):
            out[k] = schema(v)
        else:
            out[k] = v
    return out


def openai_tool(tool) -> dict:
    t = json.loads(tool) if isinstance(tool, str) else tool
    params = schema(t.get("parameters") or {"type": "object", "properties": {}})
    params.setdefault("type", "object")
    return {"type": "function", "function": {"name": safe(t["name"]), "description": t.get("description", ""), "parameters": params}}


def split(rows: list[dict], part: str, n: int | None = None, seed: int = SEED) -> list[dict]:
    """`dev`: DEV of each kind. `test`: the others, `n` of each kind when given. One fixed shuffle decides both."""
    out = []
    for kind in KINDS:
        mine = sorted((r for r in rows if r["correct_answer"] == kind), key=lambda r: r["uuid"])
        random.Random(f"{seed}:{kind}").shuffle(mine)
        out += mine[:DEV] if part == "dev" else (mine[DEV:DEV + n] if n else mine[DEV:])
    return out


def norm(v):
    """A value for comparing with the reference: folded text without punctuation at its ends, numbers as numbers."""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return Fraction(str(v))
    if isinstance(v, str):
        t = " ".join(tc.fold(v).split()).strip(" .,;:!?'\"")
        try:
            return Fraction(t)
        except (ValueError, ZeroDivisionError):
            return t
    return v


def same(value, ref) -> bool:
    """Whether a value agrees with the reference's: equal after `norm`; a list in the reference is read as the
    alternatives it allows, or as the list itself; an object agrees when each key the call gives does."""
    if isinstance(value, dict):
        refs = [ref] if isinstance(ref, dict) else [r for r in ref if isinstance(r, dict)] if isinstance(ref, list) else []
        return any(all(k in r and same(v, r[k]) for k, v in value.items()) for r in refs)
    if isinstance(value, list):
        if not isinstance(ref, list):
            return False
        whole = len(value) == len(ref) and all(same(a, b) for a, b in zip(value, ref))
        return whole or any(isinstance(r, list) and same(value, r) for r in ref)
    if isinstance(ref, list):
        return any(not isinstance(r, (list, dict)) and norm(value) == norm(r) for r in ref)
    return not isinstance(ref, dict) and norm(value) == norm(ref)


def agrees(call: dict, reference: dict, tool: dict) -> bool:
    """A released call against the benchmark's reference call: the same tool, every argument given agreeing with
    the reference's (one the reference does not have must be the schema's default), none of the reference's
    required ones missing."""
    if safe(call["name"]) != safe(reference.get("name", "")):
        return False
    ref, props = reference.get("arguments") or {}, tool["properties"]
    for k, v in call["arguments"].items():
        if k in ref:
            if not same(v, ref[k]):
                return False
        elif not ("default" in (props.get(k) or {}) and tc.same_text(v, props[k]["default"])):
            return False
    return all(k in call["arguments"] for k in tool["required"] if k in ref)


def ask_item(host: str, row: dict, post=rag_rgb._post) -> dict:
    tools = [openai_tool(t) for t in row["tools"]]
    messages = [{"role": "user", "content": row["question"]}]
    body = {"messages": messages, "temperature": 0, "max_tokens": 400, **({"tools": tools} if tools else {})}
    msg = post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]
    target = json.loads(row["target_tool"]) if row.get("target_tool") else None
    try:
        reference = json.loads(row["answers"]["tool_call"])
    except (ValueError, KeyError, TypeError):
        reference = None
    return {"uuid": row["uuid"], "kind": row["correct_answer"], "source": row.get("source"), "held_out": row.get("held_out_param"),
            "messages": messages, "tools": tools, "target": openai_tool(target)["function"]["name"] if target else None,
            "reference": reference, "reply": {"content": msg.get("content") or "", "tool_calls": msg.get("tool_calls") or []}}


def judge(row: dict, strict_enum: bool = True) -> dict:
    """Both readings of one stored reply."""
    calls = row["reply"]["tool_calls"]
    native = [dict(zip(("name", "arguments"), tc.read_call(c))) for c in calls]
    native = [c for c in native if c["arguments"] is not None]
    verdict = tc.check_all(row["tools"], row["messages"], calls, strict_enum) if calls else {"action": "none"}
    released = {"native": native, "checked": verdict["calls"] if verdict["action"] == "call" else []}
    out = {"action": verdict["action"], "native": bool(native), "checked": bool(released["checked"])}
    if row["kind"] == "tool_call" and row.get("reference"):
        specs = {s["name"]: s for s in map(tc.spec, row["tools"])}
        for arm, got in released.items():
            out[f"{arm} tool"] = any(c["name"] == row["target"] for c in got)
            out[f"{arm} agrees"] = any(c["name"] in specs and agrees(c, row["reference"], specs[c["name"]]) for c in got)
    if row["kind"] == "request_for_info":
        asked = [a["parameter"] for v in verdict.get("verdicts", []) if v["action"] == "ask" for a in v["ask"]]
        out["asks for the removed one"] = row.get("held_out") in asked
        out["asked"] = asked
    return out


def report(rows: list[dict], strict_enum: bool = True) -> dict:
    out = {}
    for kind in KINDS:
        mine = [(r, judge(r, strict_enum)) for r in rows if r["kind"] == kind]
        if not mine:
            continue
        o = {"items": len(mine), "native: a call released": sum(j["native"] for _, j in mine),
             "checked: a call released": sum(j["checked"] for _, j in mine),
             "checked: asked": sum(j["action"] == "ask" for _, j in mine), "checked: refused": sum(j["action"] == "refuse" for _, j in mine)}
        if kind == "tool_call":
            for arm in ("native", "checked"):
                o[f"{arm}: the benchmark's tool"] = sum(j.get(f"{arm} tool", False) for _, j in mine)
                o[f"{arm}: agrees with the reference call"] = sum(j.get(f"{arm} agrees", False) for _, j in mine)
        if kind == "request_for_info":
            o["checked: asked for the removed parameter"] = sum(j["asks for the removed one"] for _, j in mine)
        out[kind] = o
    for arm in ("native", "checked"):
        released = sum(out[k][f"{arm}: a call released"] for k in KINDS if k in out)
        right = out.get("tool_call", {}).get(f"{arm}: agrees with the reference call", 0)
        out[f"{arm}: of calls released, agreeing with a reference"] = {"released": released, "agree": right,
                                                                       "share": round(right / max(1, released), 4)}
    return out


def cmd_run(a) -> int:
    rows = split([json.loads(l) for l in Path(a.data).read_text(encoding="utf-8").splitlines() if l.strip()], a.part, a.n)
    done = set()
    if Path(a.out).exists():
        done = {json.loads(l)["uuid"] for l in Path(a.out).read_text(encoding="utf-8").splitlines() if l.strip()}
    todo = [r for r in rows if r["uuid"] not in done]
    hosts, lock = a.host.split(","), threading.Lock()

    def worker(k: int) -> None:
        for r in todo[k::len(hosts)]:
            try:
                answer = ask_item(hosts[k], r)
            except Exception as error:                          # noqa: BLE001 -- a failed request is rerun, not scored
                print(f"{r['uuid']}: {type(error).__name__}: {error}", file=sys.stderr)
                continue
            with lock, open(a.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(answer, ensure_ascii=False) + "\n")
    threads = [threading.Thread(target=worker, args=(k,)) for k in range(len(hosts))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"{len(rows)} items ({a.part}), {len(todo)} asked now -> {a.out}")
    return 0


def cmd_report(a) -> int:
    rows = [json.loads(l) for l in Path(a.answers).read_text(encoding="utf-8").splitlines() if l.strip()]
    r = report(rows, not a.any_enum)
    for kind in KINDS:
        if kind in r:
            print(kind + ": " + "; ".join(f"{k} {v}" for k, v in r[kind].items()))
    for arm in ("native", "checked"):
        v = r[f"{arm}: of calls released, agreeing with a reference"]
        print(f"{arm}: {v['released']} calls released, {v['agree']} agree with a reference call ({100 * v['share']:.1f}%)")
    if a.show:
        shown = collections.Counter()
        for row in rows:
            j = judge(row, not a.any_enum)
            what = ("leak" if row["kind"] != "tool_call" and j["checked"] else
                    "cost" if row["kind"] == "tool_call" and j.get("native agrees") and not j["checked"] else None)
            if what and shown[what] < a.show:
                shown[what] += 1
                verdict = tc.check_all(row["tools"], row["messages"], row["reply"]["tool_calls"], not a.any_enum)
                print(f"--- {what} ({row['kind']}, removed: {row.get('held_out')}): {row['messages'][0]['content'][:200]!r}")
                for c in row["reply"]["tool_calls"]:
                    print("    call:", tc.read_call(c))
                print("    " + (tc.question(verdict).replace("\n", "\n    ") or "released as written"))
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--host", required=True)
    r.add_argument("--data", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--part", choices=("dev", "test"), default="test")
    r.add_argument("--n", type=int, help="of each kind, how many of the test part (default: all)")
    s = sub.add_parser("report")
    s.add_argument("--answers", required=True)
    s.add_argument("--json")
    s.add_argument("--any-enum", action="store_true", help="the looser rule: a choice among an enum nobody made is released")
    s.add_argument("--show", type=int, default=0, help="print this many leaks and costs")
    a = ap.parse_args(argv)
    return {"run": cmd_run, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
