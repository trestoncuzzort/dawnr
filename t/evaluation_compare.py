#!/usr/bin/env python3
"""Exact comparisons for exported held-out clean outcomes.

    python3 t/evaluation_compare.py OUTCOMES.json --panel clean-200 \\
        --local-tag locallm-r12-s1337 --phi-tag phi4-mini-bf16 \\
        --seed-tag locallm-r12-s1337 --seed-tag locallm-r12-s1

The paired test is the exact, two-sided McNemar/binomial test over discordant
tasks. Dietterich found McNemar's test the appropriate low-Type-I-error option
when two classifiers are evaluated once on the same examples:
https://sci2s.ugr.es/keel/pdf/algorithm/articulo/dietterich1998.pdf

The exact p-value is implemented with ``math.comb`` and ``fractions.Fraction``
rather than depending on SciPy; it has the same p=0.5, two-sided binomial
meaning as SciPy's ``stats.binomtest``:
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html

The seed test asks whether stochastic LocalLLM seeds beat one *fixed* Phi clean
count. It deliberately accepts a scalar baseline, never a vector of copied Phi
results: Bouthillier et al. explain why benchmark conclusions must account for
pipeline variance rather than manufacture replicas of a deterministic run:
https://arxiv.org/abs/2103.03098
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from fractions import Fraction
from math import comb
from pathlib import Path


OUTCOME_SCHEMA_VERSION = 1


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TypeError(f"{label} must be a non-negative integer, got {value!r}")
    return value


def _fraction_text(value: Fraction) -> str:
    """Use a machine-readable exact form alongside the convenient float."""
    return f"{value.numerator}/{value.denominator}"


def exact_two_sided_binomial(successes: int, trials: int) -> Fraction:
    """Return the exact p=0.5 two-sided binomial p-value as a ``Fraction``.

    For p=0.5, the probability-ordering used by SciPy's two-sided
    ``binomtest`` reduces to twice the smaller symmetric tail. This is the
    exact test used for McNemar discordances below. See SciPy's documented
    ``stats.binomtest`` semantics:
    https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html
    """
    successes = _nonnegative_int(successes, "successes")
    trials = _nonnegative_int(trials, "trials")
    if successes > trials:
        raise ValueError(f"successes {successes} exceeds trials {trials}")
    if trials == 0:
        return Fraction(1)
    tail_end = min(successes, trials - successes)
    tail = sum(comb(trials, k) for k in range(tail_end + 1))
    return min(Fraction(1), Fraction(2 * tail, 1 << trials))


def _exact_report(b: int, c: int, *, ties: int = 0) -> dict:
    """Build the common exact-binomial report for Local wins b and Phi wins c."""
    b = _nonnegative_int(b, "b")
    c = _nonnegative_int(c, "c")
    ties = _nonnegative_int(ties, "ties")
    p_value = exact_two_sided_binomial(b, b + c)
    return {
        "b": b,
        "c": c,
        "ties": ties,
        "discordant": b + c,
        "local_minus_phi": b - c,
        "p_value": float(p_value),
        "p_value_exact": _fraction_text(p_value),
        "two_sided": True,
    }


def _normalise_clean_outcomes(outcomes: Mapping[object, object], label: str) -> dict[int, bool]:
    """Validate a task-id -> bool clean map, including JSON string task IDs."""
    normalised: dict[int, bool] = {}
    for raw_task_id, raw_clean in outcomes.items():
        try:
            task_id = int(raw_task_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label}: invalid task id {raw_task_id!r}") from exc
        if task_id in normalised:
            raise ValueError(f"{label}: duplicated task id {task_id}")
        if type(raw_clean) is not bool:
            raise ValueError(f"{label}: task {task_id} clean outcome must be true or false")
        normalised[task_id] = raw_clean
    return normalised


def paired_mcnemar(local_clean: Mapping[object, object], phi_clean: Mapping[object, object]) -> dict:
    """Compare paired clean outcomes with an exact two-sided McNemar test.

    ``b`` is the number of tasks clean only for LocalLLM and ``c`` clean only
    for Phi. Equal task-id sets are mandatory so omissions cannot silently
    change the paired population. Dietterich (1998) motivates McNemar for one
    paired evaluation of two classifiers:
    https://sci2s.ugr.es/keel/pdf/algorithm/articulo/dietterich1998.pdf
    """
    local = _normalise_clean_outcomes(local_clean, "LocalLLM")
    phi = _normalise_clean_outcomes(phi_clean, "Phi")
    if local.keys() != phi.keys():
        only_local = sorted(local.keys() - phi.keys())
        only_phi = sorted(phi.keys() - local.keys())
        raise ValueError(
            "paired McNemar needs identical task ids "
            f"(Local-only={only_local}, Phi-only={only_phi})"
        )
    b = c = both_clean = neither_clean = 0
    for task_id in local:
        local_value, phi_value = local[task_id], phi[task_id]
        if local_value and not phi_value:
            b += 1
        elif phi_value and not local_value:
            c += 1
        elif local_value:
            both_clean += 1
        else:
            neither_clean += 1
    report = _exact_report(b, c, ties=both_clean + neither_clean)
    report.update({
        "method": "exact two-sided McNemar/binomial",
        "tasks": len(local),
        "local_clean": sum(local.values()),
        "phi_clean": sum(phi.values()),
        "both_clean": both_clean,
        "neither_clean": neither_clean,
    })
    return report


def seed_sign_test(local_seed_clean_counts: Sequence[int], fixed_phi_clean_count: int) -> dict:
    """Test LocalLLM seed wins/losses against one fixed Phi clean count.

    This is an exact two-sided sign/binomial test over LocalLLM's stochastic
    seeds. ``fixed_phi_clean_count`` is intentionally a scalar: repeating a
    deterministic Phi result once per seed would invent independent baseline
    observations. The design follows the variance warning in Bouthillier et
    al., *Accounting for Variance in Machine Learning Benchmarks*:
    https://arxiv.org/abs/2103.03098
    """
    fixed_phi_clean_count = _nonnegative_int(fixed_phi_clean_count, "fixed_phi_clean_count")
    seed_counts = [_nonnegative_int(value, "LocalLLM seed clean count")
                   for value in local_seed_clean_counts]
    b = sum(value > fixed_phi_clean_count for value in seed_counts)
    c = sum(value < fixed_phi_clean_count for value in seed_counts)
    report = _exact_report(b, c, ties=len(seed_counts) - b - c)
    report.update({
        "method": "exact two-sided sign/binomial against one fixed Phi count",
        "local_seed_count": len(seed_counts),
        "fixed_phi_clean_count": fixed_phi_clean_count,
    })
    return report


def _boolean_outcomes_from_export(export: Mapping[object, object], panel: str, tag: str,
                                  field: str) -> dict[int, bool]:
    """Read one complete per-task Boolean map from score_heldout's schema-v1 JSON."""
    if export.get("schema_version") != OUTCOME_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported outcome schema {export.get('schema_version')!r}; "
            f"want {OUTCOME_SCHEMA_VERSION}"
        )
    panels = export.get("panels")
    if not isinstance(panels, Mapping) or panel not in panels:
        raise ValueError(f"outcome export has no panel {panel!r}")
    panel_data = panels[panel]
    if not isinstance(panel_data, Mapping):
        raise ValueError(f"panel {panel!r} is not an object")
    raw_ids = panel_data.get("task_ids")
    if not isinstance(raw_ids, list):
        raise ValueError(f"panel {panel!r} has no task_ids list")
    try:
        task_ids = [int(task_id) for task_id in raw_ids]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"panel {panel!r} has an invalid task id") from exc
    if len(set(task_ids)) != len(task_ids):
        raise ValueError(f"panel {panel!r} has duplicated task ids")
    tags = panel_data.get("tags")
    if not isinstance(tags, Mapping) or tag not in tags:
        raise ValueError(f"panel {panel!r} has no tag {tag!r}")
    tag_data = tags[tag]
    if not isinstance(tag_data, Mapping):
        raise ValueError(f"panel {panel!r}, tag {tag!r} is not an object")
    raw_outcomes = tag_data.get(field)
    if not isinstance(raw_outcomes, Mapping):
        raise ValueError(f"panel {panel!r}, tag {tag!r} has no {field} map")
    outcomes = _normalise_clean_outcomes(raw_outcomes, f"panel {panel!r}, tag {tag!r} {field}")
    if outcomes.keys() != set(task_ids):
        raise ValueError(f"panel {panel!r}, tag {tag!r} {field} map does not cover exactly its task ids")
    count_field = f"{field}_count"
    if tag_data.get(count_field) != sum(outcomes.values()):
        raise ValueError(f"panel {panel!r}, tag {tag!r} has an inconsistent {count_field}")
    return outcomes


def clean_outcomes_from_export(export: Mapping[object, object], panel: str, tag: str) -> dict[int, bool]:
    """Read one complete per-task clean map from score_heldout's schema-v1 JSON."""
    return _boolean_outcomes_from_export(export, panel, tag, "clean")


def spec_agrees_outcomes_from_export(export: Mapping[object, object], panel: str, tag: str) -> dict[int, bool]:
    """Read the task-specific current-spec-agreement map required by the win gate."""
    return _boolean_outcomes_from_export(export, panel, tag, "spec_agrees")


def _load_boolean_outcomes(path: Path, panel: str, tag: str, field: str) -> dict[int, bool]:
    try:
        export = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read outcome export {path}: {exc}") from exc
    if not isinstance(export, Mapping):
        raise ValueError(f"outcome export {path} is not an object")
    return _boolean_outcomes_from_export(export, panel, tag, field)


def load_clean_outcomes(path: Path, panel: str, tag: str) -> dict[int, bool]:
    """Load one clean map from a score_heldout ``--outcomes`` export."""
    return _load_boolean_outcomes(path, panel, tag, "clean")


def load_spec_agrees_outcomes(path: Path, panel: str, tag: str) -> dict[int, bool]:
    """Load the task-specific current-spec-agreement map from ``--outcomes``."""
    return _load_boolean_outcomes(path, panel, tag, "spec_agrees")


def main(argv: Sequence[str] | None = None) -> int:
    """Write comparisons as deterministic JSON so the final contract can consume them."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("outcomes", type=Path, help="schema-v1 JSON written by score_heldout --outcomes")
    ap.add_argument("--panel", required=True, help="for example clean-200 or all-232")
    ap.add_argument("--local-tag", required=True, help="the predesignated LocalLLM tag")
    ap.add_argument("--phi-tag", action="append", required=True,
                    help="a fixed Phi tag (repeatable for separately fixed baselines)")
    ap.add_argument("--seed-tag", action="append", default=[],
                    help="a LocalLLM seed tag to include in the fixed-Phi sign test (repeatable)")
    args = ap.parse_args(argv)
    if args.local_tag in args.phi_tag:
        ap.error("--local-tag cannot also be a --phi-tag")
    if len(set(args.phi_tag)) != len(args.phi_tag):
        ap.error("--phi-tag values must be distinct")
    if len(set(args.seed_tag)) != len(args.seed_tag):
        ap.error("--seed-tag values must be distinct")
    try:
        local_clean = load_clean_outcomes(args.outcomes, args.panel, args.local_tag)
        phi_clean = {tag: load_clean_outcomes(args.outcomes, args.panel, tag) for tag in args.phi_tag}
        comparisons = {tag: paired_mcnemar(local_clean, clean) for tag, clean in phi_clean.items()}
        report = {
            "schema_version": OUTCOME_SCHEMA_VERSION,
            "panel": args.panel,
            "local_tag": args.local_tag,
            "comparisons": comparisons,
        }
        if args.seed_tag:
            seed_clean_counts = {
                tag: sum(load_clean_outcomes(args.outcomes, args.panel, tag).values())
                for tag in args.seed_tag
            }
            report["seed_tags"] = args.seed_tag
            report["seed_clean_counts"] = seed_clean_counts
            report["seed_sign_tests"] = {
                tag: seed_sign_test(list(seed_clean_counts.values()), sum(clean.values()))
                for tag, clean in phi_clean.items()
            }
    except (TypeError, ValueError) as exc:
        ap.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
