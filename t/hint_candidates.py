#!/usr/bin/env python3
"""Ask a model for proof hints on the rows one kernel short, and bank them.

WS-16.2 needs 82 of the 164 MBPP-DFY programs verified by all seven kernels
with the twin refuted. It reads 57. The sweep's own blocker table names 30
lifted rows that SIX kernels already verify with the twin refuted and one does
not, each with a measured reason. Every gain this project has recorded on that
count came from the same move: read the failing row and the kernel's own
message, then write the assertion, lemma, trigger or tactic that closes it.

PRIOR ART, fetched before this file was written:

  Laurel (arXiv:2405.16792) generates Dafny helper assertions by inserting a
  placeholder AT THE VERIFIER'S ERROR LOCATION and retrieving similar lemmas;
  52.4% of its lemmas verify against 5-10% for an off-the-shelf model, and
  40.6% close on the first attempt. That is the mechanism here.

  DAISY (arXiv:2511.00125, github.com/VeriFixer/daisy, MIT) extends it to
  several assertions at once, 63.4% with one missing assertion, and carries the
  warning this file is built around: "approximately 25% [of assertions] serve
  primarily as lightweight testing aids, so removing them eliminates the
  corresponding checks, causing the verification to pass simply because there is
  nothing left to verify."

  Houdini (Flanagan and Leino, FME 2001) is how the bank is filtered: delete
  whatever the prover refutes until quiescence, and the survivors are the unique
  maximal valid subset. Needs only refutation messages, which is what we have.

So this file GENERATES and BANKS ONLY. It runs no kernel and accepts nothing.
Filtering is `hint_filter.py`, which is CPU and runs after the GPU is gone, and
which accepts a candidate only when the real VERIFIES and the twin is STILL
REFUTED -- a candidate that silences an obligation fails that second half, which
is the measurable form of DAISY's warning.

    python3 t/hint_candidates.py --host 127.0.0.1:8077 --model <name> \
        --out t/out/hints --samples 8 --temperature 0.7
"""
import argparse
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_experiment as se          # noqa: E402  (chat)
import tasks_io                       # noqa: E402
import surface                        # noqa: E402

# The 30 rows of t/COVERAGE-lifted-785.md's own blocker table, sweep r27, with
# the kernel that alone keeps each out of all seven. Read from the table, not
# guessed; the file name is the lifted task's, whose spelling differs from the
# table's (the table prints the sweep's row key).
BLOCKED = [
    ("rocq", "dafny-programs_tmp_tmpcwodh6qh_src_expt.expt"),
    ("rocq", "dafny-synthesis_task_id_472.ContainsConsecutiveNumbers"),
    ("rocq", "dafny-synthesis_task_id_598.IsArmstrong"),
    ("rocq", "dafny-synthesis_task_id_808.ContainsK"),
    ("rocq", "dafny-verify_tmp_tmphq7j0row_dataset_error_data_real_error_iseven_success_1.is_even"),
    ("rocq", "dafnyprograms_tmp_tmp74_f9k_c_invertarray.invertArray"),
    ("rocq", "formal_methods_of_software_development_tmp_tmppryvbyty_bloque_1_lab3.computeFact2"),
    ("rocq", "seng2011_tmp_tmpgk5jq85q_flex_ex2.max"),
    ("rocq", "software_building_and_verification_projects_tmp_tmp5tm1srrn_cvs_projeto_aula2.mystery1"),
    ("lean", "dafny-exercise_tmp_tmpouftptir_prac3_ex2.getEven"),
    ("lean", "dafny-exercises_tmp_tmpjm75muf__session4exercises_exercisefirstzero.mfirstCero"),
    ("lean", "dafny-synthesis_task_id_106.AppendArrayToSeq"),
    ("lean", "dafny-synthesis_task_id_578.Interleave"),
    ("lean", "dafny_tmp_tmpmvs2dmry_examples2.gcdCalc"),
    ("lean", "mfes_2021_tmp_tmpuljn8zd9_fcul_exercises_10_find.find"),
    ("lean", "seng2011_tmp_tmpgk5jq85q_ass1_ex8.getEven"),
    ("lean", "workshop_tmp_tmp0cu11bdq_workshop_answers_question6.arrayUpToN"),
    ("spark", "formalmethods_tmp_tmpvda2r3_o_dafny_invariants_ex2.pot"),
    ("spark", "metodos_formais_tmp_tmpbez22nnn_aula_2_ex2.pot"),
    ("spark", "metodos_formais_tmp_tmpql2hwcsh_invariantes_fatorial2.fatorial"),
    ("spark", "metodos_formais_tmp_tmpql2hwcsh_invariantes_potencia.pot"),
    ("spark", "prog_fun_solutions_tmp_tmp7_gmnz5f_extra_mod.mod"),
    ("spark", "programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_05_hoangkim_ex_05_hoangkim.factIter"),
    ("framac", "dafny-synthesis_task_id_240.ReplaceLastElement"),
    ("framac", "dafny-synthesis_task_id_262.SplitArray"),
    ("framac", "dafny-synthesis_task_id_460.GetFirstElements"),
    ("framac", "dafny-synthesis_task_id_577.FactorialOfLastDigit"),
    ("framac", "dafny-synthesis_task_id_86.CenteredHexagonalNumber"),
    ("framac", "dafny-verify_tmp_tmphq7j0row_test_cases_ghost.triple"),
    ("dafny", "dafny-synthesis_task_id_433.IsGreater"),
]

# What a hint may be, per kernel, and what it may never be. The refusals are not
# stylistic: each names a construct that makes a file prove anything, which every
# verifier here already bans lexically, and a candidate carrying one is dropped
# before it ever reaches a kernel.
KERNEL_NOTE = {
    "dafny": ("an `assert` statement, a `{:trigger ...}` annotation on a quantifier, "
              "or a `forall` statement", "assume, assert false, {:axiom}, {:verify false}"),
    "verus": ("an `assert(...)` with an optional `by { ... }` proof block, or explicit "
              "`#[trigger]` markers", "assume, admit, external_body, #[verifier::external]"),
    "spark": ("a `pragma Assert`, a ghost function with a Post, or a `pragma Loop_Invariant`",
              "pragma Assume, pragma Annotate with Skip_Proof"),
    "framac": ("an ACSL `//@ assert ...;` a `//@ lemma ...;` or a loop invariant",
               "//@ assume, axiomatic blocks, //@ admit"),
    "lean": ("a `have ... := by ...` step, a `simp only [...]`/`grind only [...]` lemma list, "
             "or an explicit term", "sorry, sorryAx, native_decide, axiom"),
    "rocq": ("an `assert (...) by ...` a `Lemma` with a proof, or a tactic such as "
             "`lia`/`nia`/`ring`/`induction`", "Admitted, admit, Axiom, Parameter"),
    "fstar": ("an `assert (...)` an `assume val`-free lemma with its own proof, or an "
              "SMT pattern", "assume, admit, magic (), Ambient"),
}

PROMPT = """You are closing one proof obligation in a program verifier.

A program written in a small specification language `t` has been lowered into {kernel}.
Six other independent verifiers already prove this program correct and refute a
deliberately sabotaged twin of it at a concrete input. {kernel} alone does not,
and the whole point of this task is that the program IS correct: the other six
proved it.

The `t` source:

```
{tsrc}
```

The lowered {kernel} source that {kernel} will not prove:

```
{lowered}
```

What {kernel} reported:

```
{message}
```

Write ONE hint that closes the obligation. A hint is {allowed}.

Hard rules, and a reply breaking any of them is discarded unread:
- The hint is an ADDITION. Do not delete, weaken or rewrite any existing
  precondition, postcondition, invariant, decreases clause or assertion.
- Never use: {banned}. A file that proves because nothing is left to prove is
  worse than a file that does not prove.
- The twin of this program must still be refutable afterwards. A hint that makes
  the sabotaged version provable too is a defect, not a fix.
- Reply with the hint alone, in one fenced code block, and the single line
  `INSERT AFTER: <the exact existing line to put it after>` before the block.
  No prose, no explanation.
"""


def lowered_and_message(kernel: str, task: dict) -> tuple[str, str]:
    """The lowered real program and what the kernel says about it, or ('','')."""
    mod = __import__(f"lower_{kernel}")
    try:
        src = mod.lower(task, task["body"])
    except Exception as e:                        # noqa: BLE001 a named abstain is data
        return "", f"the lowering refused this shape: {type(e).__name__}: {e}"
    ver = __import__(f"verifiers.{kernel}", fromlist=[kernel])
    suffix = {"dafny": ".dfy", "verus": ".rs", "spark": ".ads", "framac": ".c",
              "lean": ".lean", "rocq": ".v", "fstar": ".fst"}[kernel]
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / f"t_hint{suffix}"
        p.write_text(src, encoding="utf-8")
        try:
            r = ver.verify(p)
        except Exception as e:                    # noqa: BLE001
            return src, f"the verifier raised {type(e).__name__}: {e}"
    parts = [f"outcome: {getattr(r, 'outcome', '?')}"]
    for field in ("message", "detail", "stdout", "stderr", "goals", "unproved", "note"):
        v = getattr(r, field, None)
        if v:
            parts.append(f"{field}: {str(v)[:1800]}")
    return src, "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default="127.0.0.1:8077")
    ap.add_argument("--model", required=True)
    ap.add_argument("--api", default="openai", choices=["openai", "ollama"])
    ap.add_argument("--tasks-dir", default=str(HERE / "out" / "lifted-tasks"))
    ap.add_argument("--out", default=str(HERE / "out" / "hints"))
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--num-predict", type=int, default=2048)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--only-kernel", default="")
    a = ap.parse_args()

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks_dir = pathlib.Path(a.tasks_dir)
    rows = [(k, n) for k, n in BLOCKED if not a.only_kernel or k == a.only_kernel]
    print(f"{len(rows)} blocked rows, {a.samples} samples each, "
          f"{len(rows) * a.samples} replies to ask for", flush=True)

    banked = skipped = 0
    # The blocker table prints a sweep row key, which is lowercased with its
    # hyphens folded to underscores; the lifted task file keeps the corpus's own
    # spelling ("Formal-methods-of-software-development_tmp_..._Lab3.ComputeFact2").
    # A literal lookup found 9 of 30 and skipped 21 as missing, so match on the
    # normalized form, which resolves all 18 that exist.
    def norm(x: str) -> str:
        return "".join(c for c in x.lower() if c.isalnum())

    by_norm = {norm(f.stem): f for f in tasks_dir.glob("*.json")}

    for kernel, name in rows:
        path = tasks_dir / f"{name}.json"
        if not path.exists():
            path = by_norm.get(norm(name)) or path
        if not path.exists():
            print(f"SKIP {kernel:7s} {name}: no lifted task at {path.name}", flush=True)
            skipped += 1
            continue
        dest = out / f"{kernel}__{name}.json"
        if dest.exists():
            print(f"have {kernel:7s} {name}", flush=True)
            continue
        task = tasks_io.load_task(path)
        lowered, message = lowered_and_message(kernel, task)
        if not lowered:
            print(f"SKIP {kernel:7s} {name}: {message[:80]}", flush=True)
            skipped += 1
            continue
        allowed, banned = KERNEL_NOTE[kernel]
        prompt = PROMPT.format(kernel=kernel, tsrc=surface.print_task(task).rstrip(),
                               lowered=lowered[:12000], message=message,
                               allowed=allowed, banned=banned)
        replies = []
        for i in range(a.samples):
            try:
                resp = se.chat(a.host, a.model, [{"role": "user", "content": prompt}],
                               {"temperature": a.temperature if i else 0.0,
                                "seed": 1 + i, "num_predict": a.num_predict},
                               a.timeout, a.api)
            except Exception as e:                # noqa: BLE001 one bad draw is not the run
                replies.append({"sample": i, "error": f"{type(e).__name__}: {e}"})
                continue
            replies.append({"sample": i,
                            "reply": (resp.get("message") or {}).get("content", ""),
                            "done_reason": resp.get("done_reason"),
                            "reply_tokens": resp.get("eval_count")})
        dest.write_text(json.dumps({
            "kernel": kernel, "task": name, "task_file": str(path),
            "lowered_sha256": __import__("hashlib").sha256(lowered.encode()).hexdigest()[:16],
            "lowered": lowered, "message": message,
            "model": a.model, "temperature": a.temperature, "samples": a.samples,
            "replies": replies,
        }, indent=1) + "\n", encoding="utf-8")
        got = sum(1 for r in replies if r.get("reply"))
        banked += got
        print(f"bank {kernel:7s} {name}: {got}/{a.samples} replies", flush=True)

    print(f"\n{banked} candidate hints banked in {out}, {skipped} rows skipped")
    print("Filter with hint_filter.py: a candidate counts only when the real VERIFIES "
          "and the twin is STILL REFUTED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
