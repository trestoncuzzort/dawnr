"""Shared, pure canonical-prompt helper for E3 generation AND grading, so the prompt-hash binding uses ONE
render path (no duplicated logic). surface.print_task renders the frozen contract with an empty body."""
import json, hashlib, sys
sys.path.insert(0, ".")
import surface

INSTR = ("Complete the body of this t task so it verifies against the given specification. "
         "Do not change the signature, requires, ensures or spec functions.\n\n")


def contract_prompt(frozen_task, max_chars=6000):
    spec = {**frozen_task, "body": []}
    try:
        rendered = surface.print_task(spec)
    except Exception:
        return None
    if len(rendered) > max_chars:
        return None
    return [{"role": "system", "content": "Write a t program for the task."},
            {"role": "user", "content": INSTR + rendered}]


def prompt_hash(frozen_task, max_chars=10 ** 9):
    """Hash of the canonical prompt; max_chars defaults effectively-unbounded so a kept (within-budget)
    task hashes identically on the generator and grader sides."""
    m = contract_prompt(frozen_task, max_chars)
    return None if m is None else hashlib.sha1(json.dumps(m, sort_keys=True).encode()).hexdigest()[:16]
