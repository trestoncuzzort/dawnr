"""REWARD — the scoring predicate, and it returns a FLOAT.

THIS IS THE ONE THING THE CODE DOMAIN CANNOT TEACH. forge.Result hard-codes
`total = 1` with the comment "assert-based: all-or-nothing here", so its score's
first component is exactly {0.0, 1.0}. Every framework surveyed in council #18
returns a scalar: TRL `list[float]`, veRL a number, Prime Intellect's `verifiers`
`float | list[float] | dict[str, float]`, Reasoning Gym a float in [0,1], OpenAI's
python grader a float. The project's only graded channel -- a length preference --
is disabled at forge.py:64 as a reward hack, and rightly.

Row overlap is a genuine graded reward and it is not a proxy for anything: it is
the objective check itself, at finer resolution.

AND IT IS MOSTLY BOOLEAN IN PRACTICE, WHICH IS NOT WHAT ANYONE PREDICTED.
Measured over 5 banked replicates, llama3:8b-instruct-q4_K_M, 10 tasks x 8
candidates at temperature 0.8 (data/sql_screen_history.jsonl):

    candidates scored strictly between 0 and 1 : 5.5%  (sd 0.7pp)
    mean exact-match rate over tasks           : 0.5900 (sd 0.0347)
    mean SCALAR reward over tasks              : 0.6089 (sd 0.0320)

Both council seats argued that natural partial credit was the thing the code
domain could not teach, and made it the main reason to build SQL. The
measurement does not support that as stated. A wrong query usually GROUPs or
JOINs differently, so it returns a row set disjoint from the answer key and
scores 0.0 anyway. On 7 of the 10 tasks the scalar and the boolean are identical
in every replicate. Overlap is a graded metric over an outcome space that turns
out to be nearly bimodal.

WHAT IT ACTUALLY BUYS, stated at the size the evidence supports. A task whose
exact-match rate is 0.00 has zero variance and therefore contributes no gradient
at all (DAPO, arXiv 2503.14476: "a zero advantage results in no gradients"). Of
the tasks sitting at 0.00 on exact match:

    sql_alarm_share          scalar 0.125-0.292 in all 5 runs  -> reliably alive
    sql_above_line_average   scalar 0.000 in 4 runs, 0.083 in 1 -> occasionally
    sql_maint_hours_per_line scalar 0.000 in all 5 runs        -> dead either way

So the scalar rescues one task reliably and one intermittently, out of three that
the boolean writes off entirely. That is a real gain and a much smaller one than
"natural partial credit" implies. The stronger claim has been deleted rather than
reworded, per this repo's working rules.

EXACTNESS IS PRESERVED. score == 1.0 if and only if the result matches exactly
(as a multiset when order does not count, as a sequence when it does). The
denominator is max(|got|, |expected|), so padding the answer with extra rows
cannot raise the score -- the obvious reward hack for an overlap metric, closed
by construction rather than by a filter.

FLOAT COMPARISON. Values are rounded to 6 decimal places before comparison.
AVG() and a CAST-based fraction can differ in their last bits while being the
same answer, and a ground truth that depends on float bit patterns would be a
worse instrument than one that tolerates 1e-6.

WHAT A TIMEOUT SCORES IS NOT DECIDED HERE, and that is deliberate. forge.py:
504-511 is emphatic that a timeout must never become the `rejected` half of a
pair -- we do not know the answer was wrong -- while OpenAI's grader contract
scores any exception as 0. Those are different answers to the same case. This
module returns the float and reports `judgeable=False` alongside it; the caller
decides. Recording the disagreement beats resolving it silently.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .harness import extract_sql
from .runtime import QueryResult, SqliteRuntime
from .taskset import SqlTask

FLOAT_DP = 6


def _norm(v):
    return round(v, FLOAT_DP) if isinstance(v, float) else v


def _nrow(row) -> tuple:
    return tuple(_norm(v) for v in row)


def score_rows(got: list[tuple], expected: list[tuple], ordered: bool) -> float:
    """Overlap in [0, 1]. 1.0 if and only if the result is exactly right."""
    g = [_nrow(r) for r in got]
    e = [_nrow(r) for r in expected]
    if not e:
        # A task whose answer is the empty set: only the empty set is right.
        return 1.0 if not g else 0.0
    if ordered:
        matches = sum(1 for a, b in zip(g, e) if a == b)
    else:
        matches = sum((Counter(g) & Counter(e)).values())
    return matches / max(len(g), len(e))


@dataclass
class SqlScore:
    reward: float                 # in [0, 1]
    judgeable: bool               # False = we could not tell (timeout), not "wrong"
    exact: bool
    error: str = ""
    denied: str = ""
    rows_returned: int = 0
    rows_expected: int = 0
    runtime_s: float = 0.0


class SqlVerifier:
    """taskset x harness x runtime, joined here and nowhere else.

    Answer keys are computed once per (task, engine) and cached, because they are
    a function of reference_sql x fixture x ENGINE and the engine does not change
    inside a process. Recomputing them per candidate would be the same answer at
    ~10x the cost.
    """

    def __init__(self, runtime: SqliteRuntime | None = None):
        self.runtime = runtime or SqliteRuntime()
        self._keys: dict[str, list[tuple]] = {}

    def answer_key(self, task: SqlTask) -> list[tuple]:
        if task.task_sha256 not in self._keys:
            res = self.runtime.run(task.fixture, task.reference)
            if not res.ok:
                raise RuntimeError(
                    f"the REFERENCE query for {task.tid} does not run: "
                    f"{res.error}. The answer key is broken, not the candidate.")
            self._keys[task.task_sha256] = res.rows
        return self._keys[task.task_sha256]

    def score(self, completion: str, task: SqlTask) -> SqlScore:
        expected = self.answer_key(task)
        sql = extract_sql(completion)
        res: QueryResult = self.runtime.run(task.fixture, sql)
        if not res.ok:
            return SqlScore(
                reward=0.0,
                judgeable=not res.timed_out,   # a timeout is not a wrong answer
                exact=False, error=res.error, denied=res.denied,
                rows_expected=len(expected), runtime_s=res.runtime_s)
        r = score_rows(res.rows, expected, task.ordered)
        return SqlScore(reward=r, judgeable=True, exact=(r == 1.0),
                        rows_returned=len(res.rows), rows_expected=len(expected),
                        runtime_s=res.runtime_s)


# ---------------------------------------------------------------------------
# The convergent signature, as a five-line adapter rather than an argument.
#
# Council #18 found that TRL, veRL, `verifiers` and Reasoning Gym have all
# converged on "a callable taking the completion plus a task bag, returning a
# float", and that this is the cheap half of the problem. The claim is testable
# and this is the test: everything above is written to its own shape, and TRL's
# signature is reached from it in five lines. If the adapter had needed more
# than that, the convergence claim would have been wrong.
# ---------------------------------------------------------------------------
def trl_reward_func(prompts=None, completions=None, task=None, **kwargs):
    """TRL's shape: reward_func(prompts, completions, **kwargs) -> list[float]."""
    verifier = kwargs.get("verifier") or SqlVerifier()
    tasks = task if isinstance(task, (list, tuple)) else [task] * len(completions or [])
    return [verifier.score(c, t).reward for c, t in zip(completions or [], tasks)]
