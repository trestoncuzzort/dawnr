#!/usr/bin/env python3
"""WS-19 move 3: turn the verified corpus into training examples, three ways.

The corpus is 192 lifted rows reading verified / refuted in all seven kernels, 35
committed tasks, and every model answer that cleared the same gate. Each is a
program whose specification seven independent provers agreed with and whose
sabotaged twin they all refuted at a concrete witness. That is a stronger label
than any dataset this project can buy, and it is currently used once, as one
training example.

Three variants, the ones ROADMAP names as needing no new plumbing:

  nl-to-spec      the signature and the problem, write the requires and ensures
  spec-to-body    the full specification, write the body that satisfies it
  invariant-fill  the task with its loop invariants deleted, write them back

PRIOR ART, fetched before this file was written:

  ATLAS (arXiv:2512.10173) turns 2,751 verified Dafny programs into 19,385
  training examples, a 7x multiplier from the artifacts a proof already leaves.

  SAFE (arXiv:2410.15756) measures Accuracy at 2 moving 46.76 to 49.64 percent at
  a matched budget from a debugging objective over the same corpus.

  PACT (arXiv:2102.06203) is the strongest form of the argument and the reason the
  multiplier is worth more than a bigger model: at a matched 96B-token budget a
  121M model with the full co-training mix reaches 35.1 percent on 3,071 held-out
  mathlib theorems against 32.2 percent for an 837M model trained on human tactics
  alone. Seven times the parameters lost to the data. Its 167x augmentation was
  EXTRACTED from proof artifacts already on disk, not generated, and regularization
  is ruled out explicitly (the same 837M with 15 percent dropout reaches 33.6).

So this file is the generated half and it is deliberately the second lever. The
extraction half needs no model at all and is the cheaper one: the seven provers
already emit obligation lists, which premises closed a goal, and for every twin a
refutation witness, and this pipeline throws all of it away after reading the
verdict. That is CPU work and it outlives the loan of any large model.

BANKS ONLY. It runs no kernel and accepts nothing. Filtering is CPU and the rule is
the pipeline's own: a reconstructed task counts when it parses, passes check_wf,
passes the problem's own tests where it has them, and reads verified / refuted in
all seven with the twin refuted. A reconstruction that verifies because it restated
the body is the class 12.6 names, and the tests are what separate them.

    python3 t/multiplier.py --model <name> --samples 4 --out t/out/multiplier
"""
import argparse
import concurrent.futures
import copy
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_check                     # noqa: E402  (KERNELS)
import spec_experiment as se          # noqa: E402  (chat, parse_kernel_table, pool)
import surface                        # noqa: E402
import tasks_io                       # noqa: E402

VARIANTS = ("nl-to-spec", "spec-to-body", "invariant-fill")

ASK = {
"nl-to-spec": """Write the SPECIFICATION of this t task, nothing else.

You are given the task's header and its body. Write the `requires` and `ensures`
lines that belong between them. The ensures must say what the program computes, in
terms of its parameters, so that a reader who never saw the body could tell a
correct program from a wrong one.

```
{header}
{body}
```

Reply with the requires and ensures lines alone, one per line, in one fenced block.
No prose. Do not restate the body: `ensures r == <the body's expression>` is the
failure this is measuring, not the answer.""",

"spec-to-body": """Write the BODY of this t task, nothing else.

You are given the full specification. Write the statements that satisfy it.

```
{header}
{spec}
```

If the body needs a loop, give it `invariant` lines and a `decreases` line. Reply
with the body alone, the statements that go between `{{` and `}}`, in one fenced
block. No prose.""",

"invariant-fill": """Write the LOOP INVARIANTS for this t task, nothing else.

The task below is complete except that every `invariant` line has been deleted from
its loops. Write them back: enough to prove the ensures, in order, each loop's
invariants listed under it.

```
{stripped}
```

An invariant must hold when the loop is entered, be preserved by the body, and
together with the negated guard imply what the code after the loop needs. Reply
with, for each loop in order, the line `LOOP <n>:` and then its invariant lines,
in one fenced block. No prose.""",
}


def strip_invariants(task: dict) -> tuple[dict, int]:
    """The task with every loop's invariants removed, and how many loops had any."""
    out = copy.deepcopy(task)
    loops = 0

    def walk(stmts):
        nonlocal loops
        for s in stmts:
            if not isinstance(s, dict):
                continue
            if "while" in s:
                w = s["while"]
                if isinstance(w, dict):
                    # the key is "invariants", plural: a smoke test on sum_upto
                    # reported 0 loops and stripped nothing with the singular
                    if w.get("invariants"):
                        loops += 1
                        w["invariants"] = []
                    walk(w.get("body", []))
            if "if" in s and isinstance(s["if"], dict):
                walk(s["if"].get("then", []))
                walk(s["if"].get("else", []))
    walk(out.get("body", []))
    return out, loops


def header_of(text: str) -> str:
    """Everything up to and including the `returns (...)` line."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if "returns" in ln:
            return "\n".join(lines[: i + 1])
    return lines[0] if lines else ""


def spec_of(text: str) -> str:
    """The clauses above the body. Stops at `{`, because a `decreases` inside a loop
    is not part of the task's specification and a line filter over the whole text
    picks it up (found by a smoke test on sum_upto)."""
    out = []
    for ln in text.splitlines():
        if ln.startswith("{"):
            break
        if ln.strip().startswith(("requires", "ensures", "spec fun", "decreases", "=")):
            out.append(ln)
    return "\n".join(out)


def body_of(text: str) -> str:
    if "{" not in text:
        return ""
    return text[text.index("{"):]


def verified_corpus(limit: int = 0) -> list[tuple[str, pathlib.Path]]:
    """Task files whose row reads verified / refuted in all seven kernels."""
    K = list(spec_check.KERNELS)
    out: list[tuple[str, pathlib.Path]] = []
    table = HERE / "COVERAGE-lifted-785.md"
    if table.exists():
        _cols, cells = se.parse_kernel_table(table)
        lifted = HERE / "out" / "lifted-tasks"
        stems = {p.name.lower().replace("-", "_"): p for p in lifted.glob("*.json")}
        for name, row in cells.items():
            if not all(row.get(k, "").startswith("verified / refuted") for k in K):
                continue
            key = name.lower().replace("-", "_").replace("__", ".") + ".json"
            p = stems.get(key)
            if p is None:                      # the table's row key and the file's stem differ
                tail = name.rsplit("__", 1)[-1].lower()
                for stem, path in stems.items():
                    if stem.rsplit(".", 2)[-2:-1] and stem.split(".")[-2].lower() == tail:
                        p = path
                        break
            if p is not None:
                out.append((name, p))
    for p in sorted((HERE / "tasks").glob("*.t")):
        out.append(("committed:" + p.stem, p))
    return out[:limit] if limit else out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default="127.0.0.1:8077")
    ap.add_argument("--model", required=True)
    ap.add_argument("--api", default="openai", choices=["openai", "ollama"])
    ap.add_argument("--out", default=str(HERE / "out" / "multiplier"))
    ap.add_argument("--samples", type=int, default=4)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--num-predict", type=int, default=2048)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--jobs", type=int, default=8,
                    help="tasks in flight. The server is shared: this is request "
                         "slots, not VRAM, which is fixed at the server's own "
                         "--gpu-memory-utilization and owned by nobody here.")
    a = ap.parse_args()

    want = [v for v in a.variants.split(",") if v in VARIANTS]
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    corpus = verified_corpus(a.limit)
    print(f"{len(corpus)} verified tasks x {len(want)} variants x {a.samples} samples "
          f"= {len(corpus) * len(want) * a.samples} replies to ask for", flush=True)

    banked = 0

    def one(name: str, path: pathlib.Path) -> int:
        """Bank one task's replies. Returns how many came back non-empty."""
        dest = out / (name.replace("/", "_") + ".json")
        if dest.exists():
            return 0
        try:
            task = tasks_io.load_task(path)
            text = surface.print_task(task).rstrip()
        except Exception as e:                 # noqa: BLE001 one unreadable task is not the run
            print(f"SKIP {name}: {type(e).__name__}: {e}", flush=True)
            return 0
        stripped_task, n_loops = strip_invariants(task)
        try:
            stripped = surface.print_task(stripped_task).rstrip()
        except Exception:                      # noqa: BLE001
            stripped, n_loops = "", 0
        fields = {"header": header_of(text), "spec": spec_of(text),
                  "body": body_of(text), "stripped": stripped}
        rec = {"task": name, "task_file": str(path), "model": a.model,
               "temperature": a.temperature, "samples": a.samples,
               "task_sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
               "loops_with_invariants": n_loops, "reference": text, "replies": {}}
        for variant in want:
            if variant == "invariant-fill" and n_loops == 0:
                continue                       # nothing to fill; not a sample, not a failure
            prompt = ASK[variant].format(**fields)
            got = []
            for i in range(a.samples):
                try:
                    resp = se.chat(a.host, a.model, [{"role": "user", "content": prompt}],
                                   {"temperature": a.temperature if i else 0.0,
                                    "seed": 1 + i, "num_predict": a.num_predict},
                                   a.timeout, a.api)
                    got.append({"sample": i,
                                "reply": (resp.get("message") or {}).get("content", ""),
                                "done_reason": resp.get("done_reason"),
                                "reply_tokens": resp.get("eval_count")})
                except Exception as e:         # noqa: BLE001
                    got.append({"sample": i, "error": f"{type(e).__name__}: {e}"})
            rec["replies"][variant] = got
        # One temp file per task then a rename, so a task interrupted mid-flight
        # leaves nothing behind: its own resume check is dest.exists(), and a
        # half-written file would be skipped forever rather than retried.
        tmp = dest.with_suffix(".tmp")
        tmp.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
        tmp.replace(dest)
        got_n = sum(sum(1 for g in v if g.get("reply")) for v in rec["replies"].values())
        print(f"bank {name}: " + ", ".join(
            f"{v} {sum(1 for g in rec['replies'].get(v, []) if g.get('reply'))}"
            for v in rec["replies"]), flush=True)
        return got_n

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        for n in ex.map(lambda nb: one(*nb), corpus):
            banked += n

    print(f"\n{banked} replies banked in {out}")
    print("Filter on CPU: parse, check_wf, the problem's own tests, then all seven "
          "with the twin refuted. A reconstruction that verifies by restating the "
          "body is 12.6's class and the tests are what separate it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
