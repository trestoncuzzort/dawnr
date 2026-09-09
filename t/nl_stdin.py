#!/usr/bin/env python3
"""nl_stdin.py: the missing instrument COVERAGE-nl.md names but does not

build. That file found 20509 of nl/'s 24748 problems are stdin-shaped
(APPS and CodeContests: whole-program text I/O, no function signature) and
that 361 of them "would be in fragment once a signature is extracted":
their sample inputs and outputs are all-integer and their reference
solution tags no gap. What is missing is the extraction itself: a
SIGNATURE (an ordered list of typed parameters) and a parser that turns
each sample input's text into argument values and each sample output's
text into an expected result, i.e. the same (args, expected) point shape
mbpp_dfy.parse_assertion and spec_experiment.pool() produce for MBPP,
built here from raw stdin text instead of a Python assert.

    python3 nl_stdin.py --json ~/t-corpora/nl-census/nl-stdin.json \\
                         --out COVERAGE-nl-stdin.md

For every stdin-shaped problem (an APPS record whose input_output carries
no fn_name; every CodeContests record -- the same split nl_census.py
uses), a signature is inferred from the SAMPLE INPUTS ALONE by a small
grammar of common competitive-programming formats, tried in priority
order:

    (a) one line of k integers, k constant across every sample
            -> k int parameters x1..xk
    (b) first line n, second line n integers
            -> (n: int, a: seq)
    (c) first line n, then n lines of one integer each
            -> (n: int, a: seq)
    (d) first line "n m", second line n integers
            -> (n: int, m: int, a: seq)
    (e) first line t (a test count), then t blocks of one of (a)-(d)
            -> refused as `multi-case` (t has no batching) UNLESS t == 1
               in every sample, in which case the block's own signature
               is used and the constant "1" line is dropped
    (f) anything else -> refused, named `non-integer-token`, `ragged` or
        `unknown-format` (see classify_lines below)

The signature must be inferred from EVERY sample the problem carries
(APPS: every input_output inputs/outputs pair; CodeContests: every
public_tests + private_tests + generated_tests pair) and validated
against all of them: one sample that does not fit the shape the others
agreed on refuses the whole problem. The output side is separately
required to be exactly one integer token (`multi-value-output`,
`non-integer-output`). A problem is `accepted` only when every sample
clears both checks; it is additionally `in_pool` when its first Python
solution parses and nl_census.solution_tags tags no gap on it (the same
detectors COVERAGE-nl.md's AST census uses, imported rather than
reimplemented).

This is a lexical instrument over SAMPLES, not a solver: it does not run
any solution, does not look at the full hidden test suite (which is not
present in nl/'s data), and over-approximates nothing in the accepting
direction -- a problem is in the pool only if every sample it carries
parsed under the one shared signature.

Stdlib only. Streams every .jsonl.gz with nl_census._stream (gzip text
mode, one JSON object per line, nothing written to disk); the first
Python solution's JSON/list decoding is deferred until a problem has
already passed both sample checks, so the ~95% of stdin-shaped problems
that refuse never pay that cost.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import nl_census  # noqa: E402  (NL_DATA, APPS_SPLITS, CC_SPLITS, _stream,
                   # solution_tags, GAPS -- reused, not reimplemented)

REFUSAL_REASONS = ("multi-case", "non-integer-token", "ragged",
                    "unknown-format", "multi-value-output",
                    "non-integer-output")
# priority used to pick ONE reason when different samples of the same
# problem fail in different ways; see classify_problem below.
INPUT_REFUSAL_PRIORITY = ("multi-case", "non-integer-token", "ragged",
                           "unknown-format")
OUTPUT_REFUSAL_PRIORITY = ("multi-value-output", "non-integer-output")


# --------------------------------------------------------- text -> lines
def _join_sample(x) -> str:
    """APPS's `inputs`/`outputs` entries are usually a single string with
    embedded newlines, but sometimes a list of per-line strings (measured
    on apps_raw_train id 514: `['82', '28']` means the two-line input
    "82\\n28"). A list is joined with a NEWLINE, one element per line --
    unlike nl_census._flatten_text's space-join, which is fine for that
    file's unordered lexical token scan but would destroy the line
    structure this file's grammar depends on."""
    if isinstance(x, str):
        return x
    if isinstance(x, list):
        return "\n".join(_join_sample(e) for e in x)
    return "" if x is None else str(x)


def to_lines(text: str) -> list[list[str]]:
    """Sample input text -> list of whitespace-split token lists, one per
    line. \\r\\n and bare \\r are normalized to \\n first (Windows line
    endings). Every trailing blank line (including the empty element a
    final "\\n" produces) is dropped before matching -- a problem's own
    trailing newline is not a signal about its shape. An INTERIOR blank
    line is kept as a zero-token line; every grammar rule below requires
    a specific token count on every line it consumes, so an interior
    blank line reliably breaks the match and the problem is refused
    (usually `ragged` or `unknown-format`) rather than silently
    reinterpreted."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    return [ln.split() for ln in lines]


def _try_int(tok: str) -> int | None:
    try:
        return int(tok)
    except ValueError:
        return None


# ------------------------------------------------------- grammar rules
# Each matcher returns (status, data):
#   ("ok", payload)          the shape matched and every token parsed
#   ("skip", None)           this rule's precondition is not met; try
#                             the next one (NOT a refusal)
#   (reason, None)           this rule's precondition WAS met but a
#                             token or a declared count failed -- a
#                             definite refusal, no further rule is tried
# payload for "ok": ("a", k, [int,...]) | ("b", n, [int,...]) |
#                    ("c", n, [int,...]) | ("d", (n, m), [int,...]) |
#                    ("e", inner_payload)

def match_a(lines: list[list[str]]):
    if len(lines) != 1:
        return ("skip", None)
    toks = lines[0]
    if not toks:
        return ("skip", None)
    vals = [_try_int(t) for t in toks]
    if any(v is None for v in vals):
        return ("non-integer-token", None)
    return ("ok", ("a", len(toks), vals))


def match_b(lines: list[list[str]]):
    if len(lines) != 2 or len(lines[0]) != 1:
        return ("skip", None)
    n0 = _try_int(lines[0][0])
    if n0 is None:
        return ("non-integer-token", None)
    data = lines[1]
    vals = [_try_int(t) for t in data]
    if any(v is None for v in vals):
        return ("non-integer-token", None)
    if n0 < 0 or len(data) != n0:
        return ("ragged", None)
    return ("ok", ("b", n0, vals))


def match_c(lines: list[list[str]]):
    if len(lines) < 2 or len(lines[0]) != 1:
        return ("skip", None)
    n0 = _try_int(lines[0][0])
    if n0 is None:
        return ("non-integer-token", None)
    if n0 < 0 or len(lines) != n0 + 1:
        return ("skip", None)  # not this shape; let d/e have a try
    rest = lines[1:]
    if any(len(ln) != 1 for ln in rest):
        return ("skip", None)
    vals = [_try_int(ln[0]) for ln in rest]
    if any(v is None for v in vals):
        return ("non-integer-token", None)
    return ("ok", ("c", n0, vals))


def match_d(lines: list[list[str]]):
    if len(lines) != 2 or len(lines[0]) != 2:
        return ("skip", None)
    n0 = _try_int(lines[0][0])
    m0 = _try_int(lines[0][1])
    if n0 is None or m0 is None:
        return ("non-integer-token", None)
    data = lines[1]
    vals = [_try_int(t) for t in data]
    if any(v is None for v in vals):
        return ("non-integer-token", None)
    if n0 < 0 or len(data) != n0:
        return ("ragged", None)
    return ("ok", ("d", (n0, m0), vals))


def match_e(lines: list[list[str]]):
    if len(lines) < 1 or len(lines[0]) != 1:
        return ("skip", None)
    t0 = _try_int(lines[0][0])
    if t0 is None:
        return ("non-integer-token", None)
    if t0 != 1:
        return ("multi-case", None)
    inner = lines[1:]
    for m in (match_a, match_b, match_c, match_d):
        status, payload = m(inner)
        if status == "ok":
            return ("ok", ("e", payload))
        if status != "skip":
            return (status, None)
    return ("unknown-format", None)


RULES = (match_a, match_b, match_c, match_d, match_e)


def classify_lines(lines: list[list[str]]):
    """One sample's tokenized lines -> ("ok", payload) or ("refuse", reason)."""
    for m in RULES:
        status, payload = m(lines)
        if status == "ok":
            return ("ok", payload)
        if status != "skip":
            return ("refuse", status)
    return ("refuse", "unknown-format")


def rule_key(payload):
    """payload -> a hashable shape key so every sample of a problem can be
    required to have inferred the SAME signature (same rule, same k for
    rule a)."""
    tag = payload[0]
    if tag == "a":
        return ("a", payload[1])
    if tag == "e":
        return ("e",) + rule_key(payload[1])
    return (tag,)


def signature_from_key(key) -> list[list[str]]:
    if key[0] == "a":
        return [[f"x{i + 1}", "int"] for i in range(key[1])]
    if key[0] == "e":
        return signature_from_key(key[1:])
    if key[0] in ("b", "c"):
        return [["n", "int"], ["a", "seq"]]
    if key[0] == "d":
        return [["n", "int"], ["m", "int"], ["a", "seq"]]
    raise ValueError(key)


def label_from_key(key) -> str:
    if key[0] == "a":
        return f"a(k={key[1]})"
    if key[0] == "e":
        return "e:" + label_from_key(key[1:])
    return key[0]


def build_args(payload) -> list[list]:
    """payload from a successful classify_lines -> a t-typed args list,
    [["int", v], ...] / [..., ["seq", [v,...]]], in signature order."""
    tag = payload[0]
    if tag == "e":
        return build_args(payload[1])
    if tag == "a":
        return [["int", v] for v in payload[2]]
    if tag in ("b", "c"):
        _, n0, vals = payload
        return [["int", n0], ["seq", vals]]
    if tag == "d":
        _, (n0, m0), vals = payload
        return [["int", n0], ["int", m0], ["seq", vals]]
    raise ValueError(payload)


def classify_output(text: str):
    """Output sample text -> ("ok", int) or ("refuse", reason). Tokenized
    over the WHOLE normalized text (any line breaks included), so any
    amount of leading/trailing whitespace or a trailing newline is
    ignored; more than one whitespace-separated token anywhere refuses
    as `multi-value-output` regardless of which line it is on."""
    toks = text.replace("\r\n", "\n").replace("\r", "\n").split()
    if len(toks) != 1:
        return ("refuse", "multi-value-output")
    v = _try_int(toks[0])
    if v is None:
        return ("refuse", "non-integer-output")
    return ("ok", v)


# ------------------------------------------------------------ per problem
def classify_problem(samples: list[tuple[str, str]]):
    """ALL of one problem's (input_text, output_text) samples -> a dict
    with verdict, and on acceptance: grammar_rule, signature, points
    (points hold only the input-side args; the caller attaches expected
    values, already computed here, and the solution/pool check)."""
    n = len(samples)
    if n == 0:
        return {"verdict": "unknown-format", "n_samples": 0}

    per_input = [classify_lines(to_lines(inp)) for inp, _out in samples]
    oks = [(i, payload) for i, (status, payload) in enumerate(per_input)
           if status == "ok"]
    refuse_reasons = {payload for status, payload in per_input
                       if status == "refuse"}

    if len(oks) != n or len({rule_key(p) for _, p in oks}) != 1:
        if len(oks) == n:
            # every sample matched SOME rule, but not the same one
            reason = "ragged"
        else:
            reason = next((r for r in INPUT_REFUSAL_PRIORITY
                           if r in refuse_reasons), "unknown-format")
        return {"verdict": reason, "n_samples": n}

    key = rule_key(oks[0][1])
    payload_by_index = dict(oks)

    out_results = [classify_output(out) for _inp, out in samples]
    out_reasons = {payload for status, payload in out_results
                   if status == "refuse"}
    if out_reasons:
        reason = next((r for r in OUTPUT_REFUSAL_PRIORITY
                       if r in out_reasons), "multi-value-output")
        return {"verdict": reason, "n_samples": n}

    points = []
    for i in range(n):
        args = build_args(payload_by_index[i])
        expected_v = out_results[i][1]
        points.append({"args": args, "expected": ["int", expected_v]})

    return {
        "verdict": "accepted",
        "n_samples": n,
        "grammar_rule": label_from_key(key),
        "signature": signature_from_key(key),
        "points": points,
    }


# --------------------------------------------------------- first solution
def apps_first_solution(rec: dict) -> str | None:
    try:
        sols = json.loads(rec.get("solutions") or "[]")
    except (json.JSONDecodeError, TypeError):
        sols = []
    return sols[0] if sols else None


def cc_first_solution(rec: dict) -> str | None:
    for s in rec.get("solutions") or []:
        if s.get("language") in ("PYTHON3", "PYTHON"):
            return s.get("solution")
    return None


def attach_solution(result: dict, first_sol: str | None) -> None:
    """Mutates an `accepted` result in place with has_solution,
    solution_gaps (nl_census.GAPS tags on the first Python solution, read
    with nl_census.solution_tags -- the same detectors COVERAGE-nl.md's
    solution-construct census uses) and in_pool."""
    has_solution = first_sol is not None
    solution_gaps: list[str] = []
    parsed_ok = False
    if has_solution:
        tags = nl_census.solution_tags(first_sol, None, function_shaped=False)
        solution_gaps = sorted(k for k in tags if k in nl_census.GAPS)
        parsed_ok = "py2-unparseable" not in tags
    result["has_solution"] = has_solution
    result["solution_gaps"] = solution_gaps
    result["in_pool"] = has_solution and parsed_ok and not solution_gaps


def make_record(source: str, pid: str, split: str, result: dict) -> dict:
    rec = {
        "source": source,
        "id": pid,
        "split": split,
        "n_samples": result["n_samples"],
        "verdict": result["verdict"],
        "in_pool": result.get("in_pool", False),
    }
    if result["verdict"] == "accepted":
        rec["grammar_rule"] = result["grammar_rule"]
        rec["signature"] = result["signature"]
        rec["has_solution"] = result["has_solution"]
        rec["solution_gaps"] = result["solution_gaps"]
        rec["points"] = result["points"]
    return rec


# ------------------------------------------------------------- sources
def process_apps(limit: int | None = None):
    out: list[dict] = []
    pool_examples: list[dict] = []
    for split in nl_census.APPS_SPLITS:
        path = nl_census.NL_DATA / split
        if not path.exists():
            continue
        stub = split[: -len(".jsonl.gz")]
        n = 0
        for rec in nl_census._stream(path):
            if limit is not None and n >= limit:
                break
            n += 1
            try:
                io = json.loads(rec.get("input_output") or "{}")
            except (json.JSONDecodeError, TypeError):
                io = {}
            if not isinstance(io, dict) or io.get("fn_name"):
                continue  # function-shaped (or unparseable io) -- not ours
            raw_in = io.get("inputs")
            raw_out = io.get("outputs")
            samples: list[tuple[str, str]] = []
            if isinstance(raw_in, list) and isinstance(raw_out, list):
                for a, b in zip(raw_in, raw_out):
                    samples.append((_join_sample(a), _join_sample(b)))
            pid = f"{stub}:{rec.get('id')}"
            result = classify_problem(samples)
            if result["verdict"] == "accepted":
                attach_solution(result, apps_first_solution(rec))
                if result["in_pool"] and len(pool_examples) < 500:
                    pool_examples.append({
                        "source": "APPS", "id": pid,
                        "sample_input": samples[0][0],
                        "sample_output": samples[0][1],
                        "grammar_rule": result["grammar_rule"],
                        "signature": result["signature"],
                        "points": result["points"],
                    })
            out.append(make_record("APPS", pid, stub, result))
    return out, pool_examples


def process_codecontests(limit: int | None = None):
    out: list[dict] = []
    pool_examples: list[dict] = []
    for split in nl_census.CC_SPLITS:
        path = nl_census.NL_DATA / split
        if not path.exists():
            continue
        stub = split[: -len(".jsonl.gz")]
        n = 0
        for rec in nl_census._stream(path):
            if limit is not None and n >= limit:
                break
            n += 1
            samples: list[tuple[str, str]] = []
            for cat in ("public_tests", "private_tests", "generated_tests"):
                for t in rec.get(cat) or []:
                    samples.append((t.get("input", ""), t.get("output", "")))
            pid = f"{stub}:{rec.get('name')}"
            result = classify_problem(samples)
            if result["verdict"] == "accepted":
                attach_solution(result, cc_first_solution(rec))
                if result["in_pool"] and len(pool_examples) < 500:
                    pool_examples.append({
                        "source": "CodeContests", "id": pid,
                        "sample_input": samples[0][0],
                        "sample_output": samples[0][1],
                        "grammar_rule": result["grammar_rule"],
                        "signature": result["signature"],
                        "points": result["points"],
                    })
            out.append(make_record("CodeContests", pid, stub, result))
    return out, pool_examples


# --------------------------------------------------------------- render
def _block_stats(records: list[dict]) -> dict:
    n = len(records)
    accepted = [r for r in records if r["verdict"] == "accepted"]
    in_pool = [r for r in records if r["in_pool"]]
    by_rule = Counter(r["grammar_rule"] for r in accepted)
    by_reason = Counter(r["verdict"] for r in records if r["verdict"] != "accepted")
    return {"n": n, "accepted": accepted, "in_pool": in_pool,
            "by_rule": by_rule, "by_reason": by_reason}


def _render_block(w, title: str, records: list[dict]) -> None:
    st = _block_stats(records)
    n = st["n"]
    w(f"### {title}")
    w("")
    w(f"- stdin-shaped problems: {n}")
    w(f"- accepted (a signature was extracted and every sample fit it): "
      f"{len(st['accepted'])} "
      f"({100 * len(st['accepted']) / max(1, n):.1f}%)")
    w(f"- **in the pool** (accepted AND the reference solution tags no "
      f"gap): **{len(st['in_pool'])}** ({100 * len(st['in_pool']) / max(1, n):.1f}%)")
    w("")
    if st["by_rule"]:
        w("accepted signatures by grammar rule:")
        w("")
        w("| rule | problems |")
        w("|---|---|")
        for rule, c in st["by_rule"].most_common():
            w(f"| {rule} | {c} |")
        w("")
    if st["by_reason"]:
        w("refusals by reason:")
        w("")
        w("| reason | problems |")
        w("|---|---|")
        for reason, c in st["by_reason"].most_common():
            w(f"| {reason} | {c} |")
        w("")


def _fmt_point(p: dict) -> str:
    def fmt_arg(a):
        kind, v = a
        return repr(v)
    args = ", ".join(fmt_arg(a) for a in p["args"])
    return f"({args}) == {p['expected'][1]}"


def render(all_records: list[dict], pool_examples: list[dict],
           elapsed_s: float) -> str:
    by_source: dict[str, list[dict]] = defaultdict(list)
    for r in all_records:
        by_source[r["source"]].append(r)

    lines: list[str] = []
    w = lines.append
    w("# t coverage census: nl/ stdin-to-signature instrument")
    w("")
    w("COVERAGE-nl.md found 20509 of nl/'s 24748 problems are")
    w("stdin-shaped (APPS and CodeContests) and that 361 of them would be")
    w("in t's fragment once a signature is extracted: their sample inputs")
    w("and outputs are all-integer and their reference solution tags no")
    w("gap. This file builds that missing instrument: a SIGNATURE (an")
    w("ordered list of typed parameters) and a parser from sample input")
    w("text to argument values and sample output text to an expected")
    w("result, inferred by a small grammar over the samples alone, and")
    w("validated against every sample the problem carries. Method at the")
    w("end names exactly what was parsed and every decision made about")
    w("edge cases.")
    w("")
    w("## Headline")
    w("")
    _render_block(w, "nl/ stdin-shaped problems, all sources", all_records)
    w("## By source")
    w("")
    for src in ("APPS", "CodeContests"):
        _render_block(w, src, by_source.get(src, []))

    w("## Ten most common accepted signatures")
    w("")
    accepted_all = [r for r in all_records if r["verdict"] == "accepted"]
    sig_label = Counter()
    sig_shape: dict[str, list[list[str]]] = {}
    for r in accepted_all:
        label = r["grammar_rule"] + ": " + ", ".join(
            f"{name}:{typ}" for name, typ in r["signature"])
        sig_label[label] += 1
        sig_shape[label] = r["signature"]
    w("| signature | problems |")
    w("|---|---|")
    for label, c in sig_label.most_common(10):
        w(f"| `{label}` | {c} |")
    w("")

    w("## Five worked examples")
    w("")
    w("Chosen from the pool (accepted, gap-free), shortest sample input")
    w("first, so the input/signature/points line up legibly on the page.")
    w("")
    examples = sorted(pool_examples, key=lambda e: len(e["sample_input"]))[:5]
    for i, ex in enumerate(examples, 1):
        w(f"### {i}. {ex['source']} `{ex['id']}`")
        w("")
        w(f"grammar rule: `{ex['grammar_rule']}`  ")
        sig_str = ", ".join(f"{name}: {typ}" for name, typ in ex["signature"])
        w(f"signature: `({sig_str})`")
        w("")
        w("sample input:")
        w("```")
        w(ex["sample_input"])
        w("```")
        w("sample output: `%s`" % ex["sample_output"].strip())
        w("")
        w("points:")
        w("")
        for p in ex["points"][:10]:
            w(f"- `{_fmt_point(p)}`")
        if len(ex["points"]) > 10:
            w(f"- ... {len(ex['points']) - 10} more sample(s)")
        w("")

    w("## Method")
    w("")
    w(f"Run time: {elapsed_s:.1f}s. Streams every APPS and CodeContests")
    w(".jsonl.gz split with nl_census._stream (gzip text mode, one JSON")
    w("object per line; nothing is decompressed to disk). A problem is")
    w("stdin-shaped under the same split nl_census.py uses: an APPS record")
    w("whose `input_output` carries no `fn_name`, or any CodeContests")
    w("record. For APPS, every `input_output.inputs`/`outputs` pair is a")
    w("sample (not the first 3, unlike nl_census's lexical io-type scan);")
    w("an entry that is itself a list of per-line strings, rather than one")
    w("string with embedded newlines (measured on apps_raw_train id 514),")
    w("is joined with a NEWLINE per element so line structure survives.")
    w("For CodeContests, every `public_tests` + `private_tests` +")
    w("`generated_tests` pair is a sample (`generated_tests` alone runs to")
    w("hundreds per problem on this corpus).")
    w("")
    w("A signature is inferred by classifying each sample's input text")
    w("independently against the grammar in this file's docstring")
    w("(rules a-e, tried in that priority; anything left over is rule f,")
    w("a named refusal) and requiring every sample of the problem to")
    w("classify under the identical rule (and the identical k, for rule")
    w("a). One sample that does not is a whole-problem refusal, never a")
    w("partial signature: the pool over-approximates nothing, a problem")
    w("is in it only if every sample it carries parsed. When samples")
    w("disagree with each other, or a single sample fails in more than")
    w("one way across the corpus, the reported reason follows a fixed")
    w("priority -- multi-case, then non-integer-token, then ragged, then")
    w("unknown-format on the input side; multi-value-output then")
    w("non-integer-output on the output side -- rather than an arbitrary")
    w("first-seen reason.")
    w("")
    w("Decisions on edge cases not fully pinned down by the grammar's")
    w("prose:")
    w("")
    w("- Windows line endings (`\\r\\n`, bare `\\r`) are normalized to `\\n`")
    w("  before any line is split, on both the input and output side.")
    w("- Every TRAILING blank line is dropped before matching, including")
    w("  the empty element a final `\\n` produces (\"3\\n\" is one line,")
    w("  not two). An INTERIOR blank line is kept as a zero-token line,")
    w("  which fails every rule's per-line token-count check and reliably")
    w("  refuses the sample (`ragged` or `unknown-format`) rather than")
    w("  being skipped or silently reinterpreted.")
    w("- The output side is tokenized over the WHOLE normalized text with")
    w("  a plain `str.split()`, ignoring which line a token falls on, so")
    w("  the ONLY question is how many whitespace-separated tokens exist")
    w("  in total: more than one is `multi-value-output` regardless of")
    w("  formatting, exactly one is checked with `int()`.")
    w("- Rule e's test-count wrapper is only unwrapped when its count is")
    w("  1 in EVERY sample of the problem (the constant \"1\" line is then")
    w("  dropped and contributes no parameter); a count that is ever >1,")
    w("  or ever fails to parse as an int, refuses the whole problem")
    w("  (`multi-case` or `non-integer-token`) rather than being read as")
    w("  a genuine, unsupported batch -- t has no notion of batching a")
    w("  task over several independent input blocks.")
    w("- A problem with zero samples (an empty or unparseable")
    w("  `input_output`, or no test dicts under any of CodeContests's")
    w("  three categories) is refused `unknown-format` rather than given")
    w("  a reason of its own: there is nothing to classify.")
    w("- Rule b and rule c overlap exactly when n=1 (a two-line input,")
    w("  header \"1\", one data line): rule b's precondition (exactly two")
    w("  lines, one-token header) is checked first per the stated")
    w("  priority and always claims this case, so rule c's own two-line")
    w("  case never fires; it only matches n_lines == n+1 for n >= 2.")
    w("- The first Python solution (APPS: the first entry of the decoded")
    w("  `solutions` list, no language field to filter on; CodeContests:")
    w("  the first entry whose `language` is `PYTHON3` or `PYTHON`) is")
    w("  decoded and AST-tagged with `nl_census.solution_tags` ONLY for a")
    w("  problem that already passed both the input-signature and the")
    w("  output checks -- the ~95% of stdin-shaped problems that refuse")
    w("  before that point never pay for JSON-decoding or parsing a")
    w("  solution. `in_pool` requires a solution that exists, parses")
    w("  under Python 3's `ast` (not `py2-unparseable`), and tags none of")
    w("  `nl_census.GAPS` -- the identical detectors, and the identical")
    w("  `py2-unparseable` exception, COVERAGE-nl.md's solution-construct")
    w("  census uses, imported from nl_census.py rather than")
    w("  reimplemented.")
    w("")
    w("The JSON beside this report carries one record per stdin-shaped")
    w("problem: source, id, split, n_samples, verdict, in_pool, and for")
    w("an accepted problem also grammar_rule, signature, has_solution,")
    w("solution_gaps and the full points list (every sample, not a")
    w("selection) -- one `{\"args\": [[type, value], ...], \"expected\":")
    w("[\"int\", value]}` per sample, in signature order, the same")
    w("(kind, value) shape mbpp_dfy.parse_assertion and spec_experiment's")
    w("pool() use for MBPP's points.")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None, help="write the markdown report here")
    ap.add_argument("--json", default=None, help="write one JSON record per problem here")
    ap.add_argument("--limit", type=int, default=None,
                     help="cap records read per split (development only)")
    a = ap.parse_args()

    t0 = time.time()

    records: list[dict] = []
    pool_examples: list[dict] = []
    for proc in (process_apps, process_codecontests):
        recs, ex = proc(a.limit)
        records += recs
        pool_examples += ex

    elapsed = time.time() - t0
    text = render(records, pool_examples, elapsed)

    if a.out:
        out = Path(a.out).expanduser()
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {out}")
    else:
        print(text)

    if a.json:
        jpath = Path(a.json).expanduser()
        jpath.parent.mkdir(parents=True, exist_ok=True)
        jpath.write_text(json.dumps(records, indent=1), encoding="utf-8", newline="\n")
        print(f"wrote {jpath}")

    print(f"{len(records)} stdin-shaped problems in {elapsed:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
