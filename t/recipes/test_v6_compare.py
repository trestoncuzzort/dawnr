"""A paired gain cannot hide an absolute-floor regression or missing evidence."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import v6_compare as compare


def test_incremental_gain_with_all_floors_qualifies():
    assert compare.decision({'one': 17, 'seven': 12, 'spec': 27},
                            {'one': 18, 'seven': 12, 'spec': 27})['qualified']


def test_a_tie_or_better_but_below_historical_floor_does_not_qualify():
    assert not compare.decision({'one': 18, 'seven': 12, 'spec': 27},
                                {'one': 18, 'seven': 12, 'spec': 27})['qualified']
    assert not compare.decision({'one': 3, 'seven': 2, 'spec': 4},
                                {'one': 4, 'seven': 3, 'spec': 5})['qualified']


def test_more_solutions_cannot_hide_a_stronger_proof_regression_or_unsoundness():
    baseline = {'one': 20, 'seven': 15, 'spec': 30}
    assert not compare.decision(baseline, {'one': 21, 'seven': 14, 'spec': 30})['qualified']
    assert not compare.decision(baseline, {'one': 21, 'seven': 15, 'spec': 29})['qualified']
    assert not compare.decision(baseline, {'one': 21, 'seven': 15, 'spec': 30}, False)['qualified']


def test_unknown_or_weak_completeness_cannot_be_counted_as_confirmed():
    larger = {'status': 'agrees', 'draws': compare.spec_check.MIN_LARGER, 'completeness': 1}
    assert not compare.confirmed_specification({'larger': larger})
    assert not compare.confirmed_specification({'completeness': .59, 'larger': larger})
    assert not compare.confirmed_specification({'completeness': 1, 'larger': {**larger, 'draws': 0}})
    assert compare.confirmed_specification({'completeness': 1, 'larger': larger})
