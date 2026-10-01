"""memory_eval_native.py: the held-out memory items, answered by a pretrained model in its own chat format,
with dawnr's real memory recall supplying what is remembered (2026-10-01).

    python3 locallm/memory_eval_native.py --host H:P[,H:P ...] --name M --items memory-heldout.jsonl --out memory-eval.json

memory_eval.py measures the from-scratch model, which reads a remembered fact as a <|memory|> span its
training taught it. A pretrained model has no such token; what it has is a system turn. So for each item a
fresh person's store holds exactly the item's fact (dawnr_memory.store.MemoryStore, as memory_eval.py does),
the harness's SessionStart hook runs dawnr's own recall against the first message (dawnr_memory.harness_hooks,
retrieval.recall; DAWNR-MEMORY.md section 4), and whatever it returns goes into one system turn, labelled
as memory and nothing more. The reply is judged by memory_eval.judge unchanged; a fenced t block in it is the
program, as the trained model's t span would be.

What differs, stated: the span sits in a system turn ("Memory from earlier sessions with this person:"),
not a dedicated token; `memory_shown` means the recall returned something and it was placed in the
conversation; greedy decoding, --max-tokens of the model's own tokens.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "t"))

MEMORY_HEAD = "Memory from earlier sessions with this person:"


def _post(url: str, body: dict, timeout: float = 900.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def recalled(item: dict, root: Path) -> list[str]:
    """What dawnr's memory recalls for this item's person and first message (the store holds the item's fact, if any)."""
    import memory_conversations as mc
    import memory_fixtures as mfx
    from dawnr_harness.runtime import build_harness
    from dawnr_memory.store import MemoryStore
    person = mc.person_id("eval-native", item["id"])
    store = MemoryStore(root, person)
    if item.get("fact_text"):
        store.add("preference", item["fact_text"], origin="person", slot=mfx.SLOT)
    harness = build_harness({"memory": {"person": person, "root": str(root), "budget": 256}})
    try:
        return [c for c in harness.session_start(harness.session(), prompt=item["user"]) if c.strip()]
    finally:
        harness.close()


def messages_for(item: dict, contexts: list[str], system: str | None = None) -> list[dict]:
    lines = [system] if system else []
    if contexts:
        lines.append(MEMORY_HEAD + "\n" + "\n".join(contexts))
    head = [{"role": "system", "content": "\n\n".join(lines)}] if lines else []
    return head + [{"role": "user", "content": item["user"]}]


def parts_of(reply: str) -> list[dict]:
    """The reply as the evaluator's parts: its text, and a fenced t block (if any) as the program."""
    import spec_experiment as se
    parts = [{"type": "text", "text": reply}]
    block = se.find_block(reply)
    if block:
        parts.append({"type": "t", "text": block})
    return parts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", required=True)
    ap.add_argument("--name", default="model")
    ap.add_argument("--items", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--system", default=None, help="a system prompt to put before the memory (the student's own, if any)")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--scratch", type=Path, default=Path.home() / "scratch" / "memconv")
    a = ap.parse_args(argv)
    import memory_conversations as mc
    import memory_eval
    items = [json.loads(line) for line in a.items.read_text(encoding="utf-8").splitlines() if line.strip()]
    stores = mc.Stores(a.scratch / (mc.STORE_ROOT_NAME + "-eval-native-" + a.name))
    hosts = a.host.split(",")
    started = time.monotonic()
    try:
        contexts = [recalled(it, stores.root) for it in items]       # the recall runs here, once per item

        def one(k_item):
            k, (item, ctx) = k_item
            body = {"model": a.name, "messages": messages_for(item, ctx, a.system), "temperature": 0,
                    "max_tokens": a.max_tokens}
            try:
                reply = _post(f"http://{hosts[k % len(hosts)]}/v1/chat/completions", body)["choices"][0]["message"]["content"] or ""
            except Exception as e:                                  # noqa: BLE001  (a failed request is a failed item)
                reply = f"<error {type(e).__name__}>"
            return memory_eval.judge(item, parts_of(reply), bool(ctx))
        with ThreadPoolExecutor(max_workers=len(hosts)) as pool:
            rows = list(pool.map(one, enumerate(zip(items, contexts))))
    finally:
        stores.close()
    rows_path = a.out.with_suffix(".rows.jsonl")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    rows_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    out = {"model": a.name, "items": str(a.items), "max_tokens": a.max_tokens, "decoding": "greedy, memory in a system turn",
           "seconds": round(time.monotonic() - started, 1), "rows": str(rows_path), **memory_eval.summarize(rows)}
    a.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("preference_following_with_span", "preference_following_without_span",
                                          "message_over_memory", "recall_from_span", "recall_nothing_without_span",
                                          "recall_invented_without_span", "seconds")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
