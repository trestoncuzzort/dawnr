import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ten findings of the GPT-6 Astra review of 2026-10-13 on spec_check, each reproduced before its fix: a rechecked task keeps its earlier counterexample; the reference gets a copy of the drawn inputs; larger draws the requires refuses entirely are a named reason; a one-character example binds to a seq parameter as a one-element seq; the reference's answer must have the declared return's shape; a problem without examples is a named status; a deadline works from a worker thread and a nested deadline restores the enclosing one; a far draw is beyond the ordinary bound whatever the example's size; a mutant the postcondition cannot evaluate counts as rejected.


def test_main_keeps_same_task_counterexample():
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import spec_check as sc

    task = sc.surface.parse('t 0\ntask he_42__f(a: int) returns (r: int)\n  ensures r == a + 1\n{ r := a + 1; }\n')
    entry = {'fn': 'f', 'rec': {'code': 'def f(a): return a if a == 17 else a + 1'},
             'points': [{'args': [['int', 1]], 'expected': ['int', 2]}]}
    with tempfile.TemporaryDirectory() as tmp:
        here = Path(tmp) / 't'
        directory = here / 'out/spec-experiment/recheck'
        (directory / 'tasks').mkdir(parents=True)
        name = task['name']
        (directory / 'tasks' / (name + '.json')).write_text(json.dumps(task))
        key = 'recheck/' + name
        old = {'status': 'disagrees', 'task_sha256': sc.task_sha256(task),
               'args': [17], 'reference_said': 17, 'ensures': 0}
        saved_path = here / 'out/spec-disagree.json'
        saved_path.write_text(json.dumps({'checked': 1, 'tags': ['recheck'],
            'disagree': [key], 'programs': {key: sc.surface.print_task(task).strip()},
            'results': {key: old}}))
        with (
            patch.object(sc, 'HERE', here),
            patch.object(sc.se, 'pool', return_value={100042: entry}),
            patch.object(sc.se, 'parse_kernel_table', return_value=([], {name: {}})),
            patch('sys.argv', ['spec_check.py', '--only', 'all', '--n', '1',
                               '--out', str(here / 'report.md'), 'recheck'])
        ):
            sc.main()
        saved = json.loads(saved_path.read_text())
        assert key in saved['disagree']
        assert saved['results'][key]['status'] == 'disagrees'
        assert key in saved['programs']


def test_reference_mutation_does_not_change_spec_input():
    import random
    import spec_check as sc

    task = sc.surface.parse('t 0\ntask he_42__f(a: seq<seq>) returns (r: int)\n  requires len(a) > 0\n  requires len(a[0]) > 0\n  ensures r == a[0][0] + 1\n{ r := a[0][0] + 1; }\n')
    entry = {'fn': 'f', 'rec': {}, 'points': [
        {'args': [['seq-of-seq', [[1]]]], 'expected': ['int', 2]}]}
    def reference(a):
        a[0][0] += 1
        return a[0][0]
    result = sc.check_task(task, entry, 1, random.Random(1), oracle=reference,
                           drawer=lambda *args, **kwargs: [[1]])
    assert result['status'] == 'agrees', result


def test_larger_reason_detects_complete_domain_exclusion():
    import spec_check as sc
    ordinary = {'status': 'agrees', 'draws': 20}
    larger = {'status': 'no valid draws', 'draws': 0,
              'outside_requires': 200, 'requires_caps_size': True}
    assert sc.larger_reason(larger, ordinary=ordinary) == (
        'the requires closes off inputs larger than the examples')


def test_character_example_is_checked_as_a_sequence():
    import spec_check as sc
    task = sc.surface.parse('t 0\ntask he_42__f(s: seq) returns (r: int)\n  ensures r == len(s) + 1\n{ r := len(s) + 1; }\n')
    entry = {'fn': 'f', 'rec': {'test_list': ["assert f('x') == 1"]},
             'points': [{'args': [['int', 120]], 'expected': ['int', 1]}]}
    result = sc.check_points(task, entry)
    assert result['points_failed'] == 1, result


def test_reference_result_must_match_declared_return_type():
    import random
    import spec_check as sc
    task = sc.surface.parse('t 0\ntask he_42__f(a: int) returns (r: int)\n  ensures r == r\n{ r := a; }\n')
    entry = {'fn': 'f', 'rec': {}, 'points': [
        {'args': [['int', 1]], 'expected': ['seq', [1]]}]}
    result = sc.check_task(task, entry, 1, random.Random(1),
                           oracle=lambda a: [a])
    assert result['status'] != 'agrees', result


def test_no_extracted_examples_is_not_a_crash():
    import random
    import spec_check as sc
    task = sc.surface.parse('t 0\ntask he_42__f(a: int) returns (r: int)\n  ensures r == a + 1\n{ r := a + 1; }\n')
    entry = {'fn': 'f', 'rec': {'code': 'def f(a): return a + 1'}, 'points': []}
    result = sc.check_task(task, entry, 1, random.Random(1))
    assert result['status'] != 'agrees'


def test_deadline_works_in_a_worker_thread():
    import signal
    import threading
    import spec_check as sc
    if not hasattr(signal, 'SIGALRM'):
        return
    errors = []
    def worker():
        try:
            with sc.deadline(1):
                pass
        except BaseException as exc:
            errors.append(exc)
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert not errors, errors


def test_inner_deadline_does_not_cancel_outer_deadline():
    import signal
    import spec_check as sc
    if not hasattr(signal, 'SIGALRM'):
        return
    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    try:
        with sc.deadline(60):
            with sc.deadline(60):
                pass
            assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        signal.setitimer(signal.ITIMER_REAL, *old_timer)


def test_far_sequence_draw_is_still_beyond_the_example_bound():
    import random
    from unittest.mock import patch
    import spec_check as sc
    rnd = random.Random(1)
    example = list(range(50))
    with patch.object(rnd, 'random', return_value=0.0):
        value = sc.draw_beyond('seq', rnd, example, share=1.0)
    assert len(value) > len(example) + 2, len(value)


def test_undefined_mutant_counts_as_rejected():
    import random
    import spec_check as sc
    task = sc.surface.parse('t 0\ntask he_42__f(a: seq) returns (r: seq)\n  requires len(a) == 1\n  requires a[0] == 1\n  ensures r[0] == 1\n  ensures len(r) == 1\n{ r := a; }\n')
    entry = {'fn': 'f', 'rec': {}, 'points': [
        {'args': [['seq', [1]]], 'expected': ['seq', [1]]}]}
    result = sc.check_task(task, entry, 1, random.Random(1), oracle=list,
                           drawer=lambda *args, **kwargs: [1])
    assert result['mutants_rejected'] == len(sc.mutations((1,))), result
