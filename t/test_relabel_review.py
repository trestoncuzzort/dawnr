import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

# Six findings of the GPT-6 Astra review of 2026-10-13 on relabelling, each reproduced before its fix: a nested reference is not mutated into the program input; a stale kernel verdict does not certify a replaced task; one tag with two task payloads is refused; budget exhaustion is not called a disagreement; an execution rejection still counts the stated tests as passed; repeated root options keep every root.


def test_stale_kernel_verdict_does_not_certify_replaced_task():
    import json
    import tempfile
    from pathlib import Path
    import relabel
    from test_relabel import write_tag, PROGRAMS, task

    name = 'mbpp_2001__foo'
    with tempfile.TemporaryDirectory() as tmp:
        d = write_tag(Path(tmp), 'arm', {name: PROGRAMS[name]})
        # The original body was a + 2. This replacement violates its ensures at a = -1.
        replacement = task(
            f'task {name}(a: int) returns (r: int)\n'
            '  ensures r == a + 2\n'
            '{ if a < 0 { r := 0; } else { r := a + 2; } }')
        (d / 'tasks' / f'{name}.json').write_text(json.dumps(replacement))
        try:
            programs, _ = relabel.wrong_but_proven('arm', d)
        except SystemExit:
            return
        assert not programs, 'The replacement inherited the original program\'s kernel verdicts'


def test_nested_reference_mutation_does_not_change_program_input():
    from unittest.mock import patch
    import relabel

    def reference(a):
        a[0][0] *= 2
        return a[0][0]

    # Interpreter boundary for a correct, nonmutating program returning 2 * a[0][0].
    def run_point(_task, point):
        got = 2 * point['args'][0][1][0][0]
        return {'verdict': 'pass' if got == point['expected'][1] else 'fail', 'got': got}

    entry = {'rec': {}, 'fn': 'double_first', 'points': [
        {'args': [('seq-of-seq', [[1]])], 'expected': ('int', 2)}]}
    with patch.object(relabel.spec_check, 'reference', return_value=reference), \
         patch.object(relabel.spec_check, 'draw', side_effect=lambda *_: [[1]]), \
         patch.object(relabel.se, 'run_point', side_effect=run_point):
        result = relabel.execute_against_reference({}, entry, 1001, 1, 1, 'sha')
    assert result['status'] == 'exec-ok', result


def test_same_tag_with_different_task_payloads_is_refused():
    import tempfile
    import unittest
    from pathlib import Path
    import relabel
    from test_relabel import write_tag, PROGRAMS

    name = 'mbpp_2001__foo'
    with tempfile.TemporaryDirectory() as tmp:
        left, right = Path(tmp) / 'left', Path(tmp) / 'right'
        write_tag(left, 'arm', {name: PROGRAMS[name]})
        different = ('fail',
            f'task {name}(a: int) returns (r: int)\n'
            '  ensures r == a * 2\n{ r := a * 2; }')
        write_tag(right, 'arm', {name: different})
        with unittest.TestCase().assertRaisesRegex(SystemExit, 'arm'):
            relabel.graded_sets([left, right])


def test_execution_rejection_still_counts_as_passing_stated_tests():
    import relabel
    from test_relabel import entry, task

    points = [((1,), 2), ((3,), 6), ((0,), 0)]
    pool = {
        1002: entry(1002, 'dbl', 'def dbl(a):\n    return 2 * a\n', points),
        1004: entry(1004, 'other',
                    'def other(a):\n    return 2 * a if a <= 3 else 3 * a\n', points),
    }
    name = 'mbpp_2002__bar'
    program = relabel.distinct_programs([{
        'tag': 'arm', 'name': name, 'source_id': 2002, 'tests': 'fail',
        'task': task(f'task {name}(a: int) returns (r: int)\n'
                     '  ensures r == a * 2 or r == a * 3\n{ r := a * 2; }'),
    }])[0]
    outcome = relabel.relabel_program(program, [1002, 1004], pool, 100, 1)
    assert outcome['kind'] == 'admitted'
    assert outcome['tally'] == {'qualifies': 1, 'exec-fail': 1}
    row = relabel.pool_row(outcome, pool, 'v5', 100, 1, 'v5')
    assert row['relabel']['targets_passed_tests'] == 2


def test_report_does_not_call_budget_exhaustion_a_disagreement():
    import tempfile
    from collections import Counter
    from pathlib import Path
    from types import SimpleNamespace
    import relabel
    from test_relabel import PROGRAMS, task

    name = 'mbpp_2001__foo'
    program = relabel.distinct_programs([{
        'tag': 'arm', 'name': name, 'source_id': 2001, 'tests': 'fail',
        'task': task(PROGRAMS[name][1]),
    }])[0]
    outcome = {
        'program': program, 'kind': 'no-target', 'targets_tried': 1,
        'tally': Counter({'exec-budget': 1}), 'qualifying': [],
        'undecided': [{'task_id': 1001, 'status': 'exec-budget'}],
    }
    per_set = {'arm': {'rows': 1, 'seven_kernels': True,
                       'wrong_but_proven': 1, 'no_task_file': []}}
    gates = relabel.Gates(frozenset(), frozenset(), frozenset())
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        args = SimpleNamespace(n=1, seed=1, prompt_version='v5', root=[d], exclude_tags=[])
        report = d / 'report.md'
        relabel.write_report(report, args, d / 'split.json', 'v5', 1,
                             ['arm'], per_set, [program], [program], [outcome], {},
                             gates, d / 'rows.jsonl', d / 'duplicates.jsonl')
        text = report.read_text()
    assert '| pairs whose program disagreed with the reference when executed | 0 |' in text


def test_repeated_root_options_preserve_every_root():
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import relabel

    gates = relabel.Gates(frozenset(), frozenset(), frozenset())
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        roots = [d / 'machine-a', d / 'machine-b']
        for root in roots:
            root.mkdir()
        split = d / 'split.json'
        split.write_text(json.dumps({'pool': 'v5', 'train_ids': [], 'eval_ids': []}))
        with patch.object(relabel, 'load_gates', return_value=gates), \
             patch.object(relabel.se, 'pool', return_value={}), \
             patch.object(relabel, 'graded_sets', side_effect=StopIteration) as scan:
            try:
                relabel.main(['--split', str(split), '--out', str(d / 'out.jsonl'),
                              '--root', str(roots[0]), '--root', str(roots[1])])
            except StopIteration:
                pass
            assert scan.call_args.args[0] == roots
