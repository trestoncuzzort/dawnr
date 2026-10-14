import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Five findings of the review on the lift census: an unchecked lift is undecided; a recorded checker failure is lifted but not counted; a generated-task well-formedness failure is undecided; a boolean-only record keeps its gaps; the gap fallback excludes the non-blocking detectors.


def test_unchecked_method_remains_undecided():
    from types import SimpleNamespace
    from lift_census import _row_from_method_outcome

    # State after lifting with the check stage skipped.
    record = SimpleNamespace(
        rewrites=[], rename_map={}, twin_rung=None, warnings=[],
        checker_verdicts={}, differential_verdict=None,
    )
    outcome = SimpleNamespace(method='M', refusal=None, record=record)
    census = {'file': 'm.dfy', 'in_fragment': True, 'gaps': []}
    row = _row_from_method_outcome(census, outcome)
    assert row.disagreement == 'undecided'


def test_checker_failure_is_lifted_but_not_counted():
    from lift_census import CensusRow, summarize

    row = CensusRow(
        file='m.dfy', method='M', in_fragment=True, gaps=[],
        lifter_verdict='lifted',
        checker_verdicts={'dafny': 'UNPROVED'},
    )
    summary = summarize([row])
    assert summary.method_lifted == 1
    assert summary.method_counted == 0


def test_generated_wf_failure_does_not_blame_census():
    from lift_ast import Refusal
    from lift_census import disagreement_verdict

    refusal = Refusal(
        reason='check-wf-failed', token='unbound generated identifier tmp',
        line=0, stage='check',
    )
    census = {'file': 'm.dfy', 'in_fragment': True, 'gaps': []}
    assert disagreement_verdict(census, refusal, False) == 'undecided'


def test_boolean_only_policy_gap_is_undecided():
    from lift_census import disagreement_verdict

    census = {'file': 'a.dfy', 'in_fragment': False, 'array': True}
    assert disagreement_verdict(census, None, True) == 'undecided'


def test_gap_fallback_excludes_nonblocking_detectors():
    from lift_census import _census_gaps_dict

    census = {
        'file': 'a.dfy', 'in_fragment': False,
        'has-method': True, 'method-with-ensures': True, 'array': True,
    }
    assert _census_gaps_dict(census) == ['array']
