"""memory_eval.py: judge a chat model on held-out memory items, the span the real recall's own, the engine real.

    python3 locallm/memory_eval.py --model <dir> --items memory-heldout.jsonl --out memory-eval.json
    python3 locallm/memory_eval.py --report <runs dir>          # arms and seeds side by side, from their files

Each item (memory_conversations.py heldout) is a first user turn, with or without a memory span installed on
a fresh person (memory_conversations.Stores; the same person id never carries a span in one item and not the
other, so `with` and `without` are the same task under two conditions). The model then generates greedily
through engine.py with a real Harness carrying dawnr's own memory (dawnr_memory.harness_hooks): if the
checkpoint has no <|memory|> token (chat.has_memory_tokens), engine.py's span.session_start_ids shows it
nothing regardless of what the store holds (DAWNR-MEMORY.md, dawnr_memory/span.py), which is itself part of
what this measures -- a model with no memory training cannot use memory it is handed. What is counted, from the
sampled tokens only (chat.final_program, never the forced <|memory|> span itself):

* `use`: the parameter name in the model's program matches the span's preference (and the program still passes
  the task's own Example lines: a coincidental rename that breaks the program does not count as following it),
  with the span installed and without, on the same held-out tasks and people;
* `override`: the person's first message names a value for this turn; the parameter name matches the message,
  not the span's remembered value;
* `recall`: "what do you remember about me?", with a span installed: the answer names the span's own preference
  value; with none: the answer says it does not remember, rather than inventing a preference (a backtick-quoted
  name, or a preference verb, with nothing in the store to have grounded it);
* `unapplied`: a style preference over a task it does not touch; the program is unchanged.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "t"))

NOTHING_WORDS = ("nothing yet", "don't remember", "do not remember", "nothing about you", "no memories",
                 "haven't told", "have not told", "don't know anything", "do not know anything")
INVENTED_PATTERN = re.compile(r"`[a-zA-Z_][a-zA-Z0-9_]*`|\bprefers?\b|\balways (?:names|uses)\b")


def norm(program: str | None) -> str:
    return " ".join((program or "").split())


def program_passes(program: str | None, examples: list[str]) -> bool:
    import t_tool
    import tool_fixtures as fx
    if not program:
        return False
    return fx.passes(t_tool.call(program, "\n".join(examples)))


def followed_name(program: str | None, name: str, examples: list[str]) -> bool:
    """The program declares a sequence parameter called `name`, and still passes the task's own examples."""
    import memory_fixtures as mfx
    if not program or not program_passes(program, examples):
        return False
    return name in mfx.seq_params(program)


def said_nothing(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in NOTHING_WORDS)


def invented(text: str) -> bool:
    return bool(INVENTED_PATTERN.search(text)) and not said_nothing(text)


def judge(item: dict, parts: list[dict], memory_shown: bool) -> dict:
    import chat
    sampled_parts = [p for p in parts if p["type"] in ("text", "t", "tool")]
    sampled = "\n".join(p["text"] for p in sampled_parts)
    program = chat.final_program(parts) if parts else None
    got = {"id": item["id"], "category": item["category"], "span": item.get("span"), "memory_shown": memory_shown,
          "program": program, "text": sampled[:1000]}
    if item["category"] == "use":
        got["followed"] = followed_name(program, item["preference"], item["examples"])
        got["kept_old_name"] = followed_name(program, item["old_name"], item["examples"])
        got["program_passes"] = program_passes(program, item["examples"])
    elif item["category"] == "override":
        got["followed_message"] = followed_name(program, item["said"], item["examples"])
        got["used_memory_instead"] = followed_name(program, item["remembered"], item["examples"])
        got["program_passes"] = program_passes(program, item["examples"])
    elif item["category"] == "recall":
        if item["span"]:
            got["correct"] = bool(re.search(r"(?<![A-Za-z0-9_])" + re.escape(item["preference"])
                                            + r"(?![A-Za-z0-9_])", sampled))
        else:
            got["correct"] = said_nothing(sampled)
            got["invented"] = invented(sampled)
    elif item["category"] == "unapplied":
        got["unchanged"] = norm(program) == norm(item["program"])
        got["program_passes"] = program_passes(program, item["examples"])
    return got


def rate(rows, key, where=lambda r: True) -> dict:
    sel = [r for r in rows if where(r) and key in r]
    k = sum(bool(r[key]) for r in sel)
    return {"k": k, "n": len(sel), "rate": round(k / len(sel), 4) if sel else None}


def summarize(rows: list[dict]) -> dict:
    by = defaultdict(list)
    for r in rows:
        by[r["category"]].append(r)
    use, override, recall, unapplied = by["use"], by["override"], by["recall"], by["unapplied"]
    return {
        "preference_following_with_span": rate(use, "followed", lambda r: r["span"]),
        "preference_following_without_span": rate(use, "followed", lambda r: not r["span"]),
        "message_over_memory": rate(override, "followed_message"),
        "kept_memory_over_message": rate(override, "used_memory_instead"),
        "recall_from_span": rate(recall, "correct", lambda r: r["span"]),
        "recall_nothing_without_span": rate(recall, "correct", lambda r: not r["span"]),
        "recall_invented_without_span": rate(recall, "invented", lambda r: not r["span"]),
        "unapplied_unchanged": rate(unapplied, "unchanged"),
        "memory_shown_when_installed": rate([r for r in rows if r["span"]], "memory_shown"),
        "items": dict(Counter(r["category"] for r in rows)),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", type=Path)
    ap.add_argument("--items", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--device", default=None)
    ap.add_argument("--limit", type=int, default=0, help="first N items only (a smoke run)")
    ap.add_argument("--scratch", type=Path, default=Path.home() / "scratch" / "memconv")
    ap.add_argument("--report", type=Path, default=None, help="a runs directory: tabulate every memory-eval.json in it")
    ap.add_argument("--json", type=Path, default=None, help="with --report: also write the table here")
    a = ap.parse_args(argv)
    if a.report:
        return report(a.report, a.json)
    import chat
    import memory_conversations as mc
    from checkpoint import load_checkpoint
    from engine import Engine, reply_parts
    items = [json.loads(line) for line in a.items.read_text(encoding="utf-8").splitlines() if line.strip()]
    if a.limit:
        items = items[:a.limit]
    model, tok, _ = load_checkpoint(a.model, a.device)
    stores = mc.Stores(a.scratch / (mc.STORE_ROOT_NAME + "-eval-" + a.model.name))
    rows, started = [], time.monotonic()
    rows_path = a.out.with_suffix(".rows.jsonl")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with rows_path.open("w", encoding="utf-8") as f:
            from dawnr_harness.runtime import build_harness
            from dawnr_memory.store import MemoryStore
            import memory_fixtures as mfx
            for item in items:
                person = mc.person_id("eval", item["id"])
                store = MemoryStore(stores.root, person)
                if item.get("fact_text"):
                    store.add("preference", item["fact_text"], origin="person", slot=mfx.SLOT)
                harness = build_harness({"memory": {"person": person, "root": str(stores.root), "budget": 256}})
                session = harness.session()
                tokens = chat.render_for_completion(tok, {"messages": [{"role": "user", "content": item["user"]}]})
                engine = Engine(model, tok, harness=harness)
                results, _ = engine.generate_batch(tokens, 1, max_tokens=a.max_tokens, temperature=0.0, seed=0,
                                                   sessions=[session])
                parts = reply_parts(tok, results[0])
                memory_shown = any(p["type"] == "memory" for p in parts)
                got = judge(item, parts, memory_shown)
                rows.append(got)
                f.write(json.dumps(got, ensure_ascii=False) + "\n")
                harness.close()
    finally:
        stores.close()
    out = {"model": str(a.model), "items": str(a.items), "max_tokens": a.max_tokens, "decoding": "greedy",
           "seconds": round(time.monotonic() - started, 1), "rows": str(rows_path), **summarize(rows)}
    a.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("preference_following_with_span", "preference_following_without_span",
                                          "message_over_memory", "recall_from_span",
                                          "recall_nothing_without_span", "seconds")}))
    return 0


# ------------------------------------------------------------------ report --

def report(runs: Path, out: Path | None = None) -> int:
    """Every <arm>-s<seed>/memory-eval.json (and chat-eval.json, if the run also carries the t-task guard's
    numbers) under runs, side by side, read never recomputed -- tool_eval.py --report's counterpart."""
    from statistics import mean
    table = defaultdict(dict)
    for path in sorted(runs.glob("*-s*/memory-eval.json")):
        m = re.match(r"(.+)-s(\d+)$", path.parent.name)
        arm, seed = m.groups()
        entry = table[arm][int(seed)] = {"memory": json.loads(path.read_text())}
        if (path.parent / "chat-eval.json").is_file():
            entry["dev"] = json.loads((path.parent / "chat-eval.json").read_text())
    summary = {}
    for arm, seeds in sorted(table.items()):
        rows = {}
        for seed, r in sorted(seeds.items()):
            m, d = r["memory"], r.get("dev", {})
            dev = (d.get("dev") or {}) if d else {}
            val = (d.get("val") or {}) if d else {}
            rows[seed] = {
                "preference_following_with_span": (m["preference_following_with_span"] or {}).get("rate"),
                "preference_following_without_span": (m["preference_following_without_span"] or {}).get("rate"),
                "message_over_memory": (m["message_over_memory"] or {}).get("rate"),
                "recall_from_span": (m["recall_from_span"] or {}).get("rate"),
                "recall_nothing_without_span": (m["recall_nothing_without_span"] or {}).get("rate"),
                "recall_invented_without_span": (m["recall_invented_without_span"] or {}).get("rate"),
                "unapplied_unchanged": (m["unapplied_unchanged"] or {}).get("rate"),
                "memory_shown_when_installed": (m["memory_shown_when_installed"] or {}).get("rate"),
                "pass_all_133": (dev.get("examples_all_pass") or 0) + (val.get("examples_all_pass") or 0) if d else None,
                "dev_well_formed": dev.get("well_formed"),
            }
        summary[arm] = rows
    means = {}
    for arm, rows in summary.items():
        cols = {}
        for row in rows.values():
            for k, v in row.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    cols.setdefault(k, []).append(v)
        means[arm] = {k: round(sum(v) / len(v), 4) for k, v in cols.items() if len(v) == len(rows)}
    summary["_means"] = means
    arms = [a for a in means if a != "_means"]
    if len(arms) >= 2 and all("pass_all_133" in means[a] for a in arms[:2]):
        base, plus = arms[0], arms[1]
        guard = {"base": base, "plus": plus,
                "pass_all_133_holds": means[plus]["pass_all_133"] >= means[base]["pass_all_133"] - 2,
                "dev_well_formed_holds": means[plus].get("dev_well_formed", 0) >= means[base].get(
                    "dev_well_formed", 0) - 5}
        guard["verdict"] = ("RECOMMEND as mid-stage data" if guard["pass_all_133_holds"]
                           and guard["dev_well_formed_holds"] else "stay opt-in: the t-task guard failed")
        summary["_t_task_guard"] = guard
    print(json.dumps(summary, indent=2))
    if out is not None:
        out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
