"""memory_metrics.py: the metrics and file hooks the memory and per-person learning tracks
report through (AMBITION.md's "dawnr grows with the person using it": "to remember the
person across sessions", "to learn from every session", "a personality that grows per
person"). Neither track is built yet -- AMBITION.md marks all three "being built" -- so this
module only defines what a finished one must write for locallm/dawnr_report.py to read, and
the arithmetic over that file, so the two land independently of each other and of this report
and the report never blocks on either (dawnr_report.py's own rule: it only reads what a stage
already wrote).

Long-term memory recall is scored the way LongMemEval does it (Wu et al., "LongMemEval:
Benchmarking Chat Assistants on Long-Term Interactive Memory", arXiv:2410.10813): accuracy of
an answer against a probe question grounded in what the assistant was actually told, with
abstention scored separately from a wrong answer. That separation matters more here than it
does for LongMemEval's benchmark, because dawnr's own rule is that an honest refusal beats a
false verdict (AGENTS.md rule 2): a memory system that says "I was not told that" about a fact
it never received is right, and one that invents a plausible-sounding answer instead is worse
than one that says nothing, so this counts hallucination-on-an-untold-fact as its own number
rather than folding it into a single accuracy score. Personalization is scored as a pair, not
a single number, against AMBITION.md's own bar for per-person learning -- "gets better at
their tasks without getting worse at everything else" -- because a per-person model that only
improves on its own tasks and one that only avoids regressing are both a different, worse
system than the one that does both at once.

FILE FORMATS (JSONL, one record per line; a missing or empty file is "not available" to
dawnr_report.py, never an error -- there is nothing to divide by yet, and rule 1 is that a
number without the run that produced it does not count):

memory recall (one line per probe question asked of the person's stored memory):
    {"person_id": str, "session": int, "probe": str, "expected": str | null,
     "got": str, "correct": bool, "abstained": bool}
  "expected" is null exactly when the fact was never told to dawnr in any prior session (the
  abstention case a correct memory must handle); "abstained" is whatever the assistant
  actually did (answered "I don't have that"), independent of whether a true answer exists,
  so recall on told facts and the false-abstention/hallucination rates are all computable from
  the same rows without re-running anything.

personalization (one line per person-task probe, graded once with the shared model only and
once with that person's adapter applied):
    {"person_id": str, "task": str, "with_adapter": float, "without_adapter": float,
     "general_loss_with_adapter": float, "general_loss_baseline": float}
  the two task scores are the same probe graded the same way -- t/rl_reward.py's tier turned
  into a 0..1 number, a pass rate, or any score the learning track picks, documented where it
  writes the file, as long as higher is better and the two are comparable; the two losses are
  nats/token on the same held-out general-English shard (dawnr_pipeline.heldout_loss), with
  and without that person's adapter applied, so a personalization gain that costs general
  ability is visible rather than averaged away.
"""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_RECALL_KEYS = ("person_id", "probe", "expected", "got", "correct", "abstained")
REQUIRED_PERSONALIZATION_KEYS = ("person_id", "task", "with_adapter", "without_adapter",
                                 "general_loss_with_adapter", "general_loss_baseline")


def read_jsonl(path: Path) -> list[dict]:
    """Every non-blank line of a JSONL file as a dict. A missing file is empty, not an error:
    the caller decides whether "no rows" means "not available"."""
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _ratio(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


def _check_keys(rows: list[dict], required: tuple[str, ...], what: str) -> None:
    for row in rows:
        missing = [k for k in required if k not in row]
        if missing:
            raise ValueError(f"{what} row is missing {missing}: {row!r}")


def recall_metrics(rows: list[dict]) -> dict:
    """LongMemEval-shaped accuracy (arXiv:2410.10813) over one person's (or every person's,
    pooled) memory probes: recall on facts the person actually told dawnr, the false-
    abstention rate on those same facts (said "I don't know" about something it was told --
    a forgetting failure), and, on facts never told, the correct-abstention rate against its
    mirror, hallucination on an untold fact (a fabrication, the worse of the two failures per
    AGENTS.md rule 2). Raises on an empty list rather than returning an all-null row, so a
    caller that forgot to check "any rows at all" first gets a loud error instead of a report
    that silently prints every field as "-"."""
    if not rows:
        raise ValueError("recall_metrics: no probes")
    _check_keys(rows, REQUIRED_RECALL_KEYS, "memory recall")
    told = [r for r in rows if r["expected"] is not None]
    untold = [r for r in rows if r["expected"] is None]
    recalled = sum(1 for r in told if r["correct"] and not r["abstained"])
    false_abstention = sum(1 for r in told if r["abstained"])
    hallucinated = sum(1 for r in untold if not r["abstained"])
    people = sorted({r["person_id"] for r in rows if r.get("person_id") is not None})
    return {"probes": len(rows), "people": len(people), "told": len(told), "untold": len(untold),
            "recall": _ratio(recalled, len(told)), "false_abstention_rate": _ratio(false_abstention, len(told)),
            "correct_abstention_rate": _ratio(len(untold) - hallucinated, len(untold)),
            "hallucinated_on_untold_fact_rate": _ratio(hallucinated, len(untold))}


def personalization_metrics(rows: list[dict]) -> dict:
    """Uplift on the person's own tasks against regression on held-out general English, the
    pair AMBITION.md's per-person learning row asks for rather than one blended score.
    "net_positive_share" is the fraction of probes where both held at once (uplift > 0 and no
    general-loss regression): the number a caller should read first, since either half alone
    (task uplift with a forgotten general model, or an unmoved general loss with no uplift)
    both describe a different track failing, not a success this one records on its own."""
    if not rows:
        raise ValueError("personalization_metrics: no probes")
    _check_keys(rows, REQUIRED_PERSONALIZATION_KEYS, "personalization")
    uplift = [r["with_adapter"] - r["without_adapter"] for r in rows]
    forgetting = [r["general_loss_with_adapter"] - r["general_loss_baseline"] for r in rows]
    people = sorted({r["person_id"] for r in rows if r.get("person_id") is not None})
    both_good = sum(1 for u, f in zip(uplift, forgetting) if u > 0 and f <= 0)
    return {"probes": len(rows), "people": len(people),
            "mean_task_uplift": round(sum(uplift) / len(uplift), 4),
            "task_improved_share": _ratio(sum(1 for u in uplift if u > 0), len(uplift)),
            "mean_general_loss_change": round(sum(forgetting) / len(forgetting), 4),
            "general_regressed_share": _ratio(sum(1 for f in forgetting if f > 0), len(forgetting)),
            "net_positive_share": _ratio(both_good, len(rows))}
