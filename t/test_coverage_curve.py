"""t/coverage_curve.py: Codex's unbiased pass@k over graded answer sets, and what a doubling of the answers adds."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import coverage_curve as cc  # noqa: E402


def test_the_curve_is_the_expected_number_of_problems_with_a_counted_answer_among_k_sets():
    # three problems over four sets: one counted in every set, one in exactly one, one in none
    curve = cc.expected([4, 1, 0], 4)
    assert curve == pytest.approx([1 + 1 / 4, 1 + 2 / 4, 1 + 3 / 4, 2.0])
    # with every set drawn it is the pooled count, and it never falls as more are drawn
    assert cc.expected([0, 2, 5, 17], 17)[-1] == 3 and all(b >= a for a, b in zip(curve, curve[1:]))
    # Codex's eq. 1 for one problem: n = 5 sets, counted in c = 2, k = 2 drawn
    assert cc.expected([2], 5)[1] == pytest.approx(1 - math.comb(3, 2) / math.comb(5, 2))


def test_the_estimator_is_not_the_biased_one():
    # 1 - (1 - c/n)^k overstates what k of n distinct sets can hold; the estimator used is exact for sets drawn without replacement
    assert cc.expected([1], 2)[1] == 1.0 and 1 - (1 - 1 / 2) ** 2 == 0.75


def test_what_each_doubling_adds():
    curve = [1.0, 2.0, 2.5, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0]
    assert cc.doublings(curve) == [(1, 2, 1.0), (2, 4, 1.5), (4, 8, 2.5)]


def test_problems_are_counted_per_set_at_the_asked_level(monkeypatch):
    levels = {"a": {1: (7, 7, True, True), 2: (0, 3, True, True), 3: (1, 1, True, True)},
              "b": {1: (1, 1, True, True), 2: (0, 0, True, False), 3: (0, 1, True, True)}}
    monkeypatch.setattr(cc.score_levels, "tag_levels", lambda tag, ids, verdicts, mc, larger: levels[tag])
    assert cc.counts(["a", "b"], {1, 2, 3}, {}, 1, 0.6, True) == {1: 2, 2: 0, 3: 1}
    assert cc.counts(["a", "b"], {1, 2, 3}, {}, 7, 0.6, True) == {1: 1, 2: 0, 3: 0}
    text = cc.render(["a", "b"], {1: 2, 2: 0, 3: 1}, cc.expected([2, 0, 1], 2))
    assert "| problems expected to be counted | 1.5 | 2.0 |" in text and "From 1 to 2 answers: +0.5 problems." in text
    assert "Counted in exactly one of the 2 sets: 1 problems; in none: 1 of 3." in text
