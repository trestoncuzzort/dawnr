import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Seven findings of the GPT-6 Astra review of 2026-10-13 on the Lean lowering, each reproduced before its fix: the placeholder branch of a single-invariant loop is proved unreachable (preservation) instead of proving the placeholder's specification; a return before the loop is refused by name; match binders that clash with an outer substitution are renamed; a recursive task's measure owes its definedness; an exit certificate must carry the frame; an ensures-level undefined certificate needs the specification to reach the subexpression; spec functions are declared before the helpers that call them.


@pytest.mark.skipif(shutil.which("lean") is None, reason="lean is not installed")
def test_invariant_failure_cannot_become_a_proof():
    from lower_lean import Lower
    import pathlib, subprocess, tempfile
    I = lambda n: {'int': n}
    V = lambda n: {'var': n}
    O = lambda op, *args: {'op': op, 'args': list(args)}
    body = [
        {'assign': ['r', I(0)]},
        {'var': {'name': 'i', 'type': 'int', 'init': I(0)}},
        {'while': {'cond': O('!=', V('i'), I(1)),
                   'invariants': [O('==', V('i'), I(0))],
                   'decreases': O('-', I(1), V('i')),
                   'body': [{'assign': ['i', I(1)]}, {'assign': ['r', I(1)]}]}}]
    task = {'name': 'bad_preservation', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [O('==', V('r'), I(0))], 'body': body}
    try:
        src = Lower(task, body).lower()
    except NotImplementedError:
        return
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / 'test.lean'
        path.write_text(src)
        p = subprocess.run(['lean', str(path)], capture_output=True, text=True)
    assert p.returncode != 0 or 'sorryAx' in p.stdout + p.stderr, 'Kernel accepted the placeholder, not the source program'


@pytest.mark.skipif(shutil.which("lean") is None, reason="lean is not installed")
def test_return_before_single_loop_is_not_discarded():
    from lower_lean import Lower
    import pathlib, subprocess, tempfile
    I = lambda n: {'int': n}
    V = lambda n: {'var': n}
    O = lambda op, *args: {'op': op, 'args': list(args)}
    body = [
        {'return': ['r', I(1)]},
        {'var': {'name': 'i', 'type': 'int', 'init': I(0)}},
        {'while': {'cond': O('<', V('i'), I(1)),
                   'invariants': [O('and', O('<=', I(0), V('i')), O('<=', V('i'), I(1)))],
                   'decreases': O('-', I(1), V('i')),
                   'body': [{'assign': ['i', O('+', V('i'), I(1))]}]}},
        {'assign': ['r', I(2)]}]
    task = {'name': 'prefix_return', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [O('==', V('r'), I(2))], 'body': body}
    try:
        src = Lower(task, body).lower()
    except NotImplementedError:
        return
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / 'test.lean'
        path.write_text(src)
        p = subprocess.run(['lean', str(path)], capture_output=True, text=True)
    assert p.returncode != 0 or 'sorryAx' in p.stdout + p.stderr, 'Source returns 1, but its generated contract proves 2'


@pytest.mark.skipif(shutil.which("lean") is None, reason="lean is not installed")
def test_match_does_not_capture_saved_outer_value():
    from lower_lean import Lower
    import pathlib, subprocess, tempfile
    body = [
        {'var': {'name': 'saved', 'type': 'int', 'init': {'var': 'x'}}},
        {'return': ['r', {'match': {
            'scrutinee': {'var': 'box'},
            'arms': [{'ctor': 'Mk', 'binders': ['x'], 'body': {'var': 'saved'}}]}}]}]
    task = {'name': 'capture_probe',
            'params': [{'name': 'x', 'type': 'int'},
                       {'name': 'box', 'type': {'datatype': 'UserBox'}}],
            'returns': [{'name': 'r', 'type': 'int'}],
            'datatypes': [{'name': 'UserBox', 'ctors': [
                {'name': 'Mk', 'fields': [{'name': 'payload', 'type': 'int'}]}]}],
            'requires': [], 'ensures': [{'bool': True}], 'body': body}
    src = Lower(task, body).lower()
    src += '\nexample : capture_probe_t 3 (UserBox.Mk 9) = 3 := by decide\n'
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / 'test.lean'
        path.write_text(src)
        p = subprocess.run(['lean', str(path)], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr


def test_recursive_measure_requires_definedness():
    from lower_lean import Lower
    I = lambda n: {'int': n}
    V = lambda n: {'var': n}
    O = lambda op, *args: {'op': op, 'args': list(args)}
    dec = O('+', V('n'), O('div', I(1), I(0)))
    body = [{'if': {'cond': O('>', V('n'), I(0)),
                    'then': [{'return': ['r', {'call': {'fun': 'countdown',
                              'args': [O('-', V('n'), I(1))]}}]}],
                    'else': [{'return': ['r', I(0)]}]}}]
    task = {'name': 'countdown', 'params': [{'name': 'n', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [O('==', V('r'), I(0))], 'decreases': dec, 'body': body}
    lw = Lower(task, body)
    obligation = lw.dcond(dec, {}, dict(lw.types))
    assert obligation is not None
    try:
        src, _ = lw.lower_rec()
    except NotImplementedError:
        return
    assert obligation in src, 'The undefined measure has no emitted definedness obligation'


@pytest.mark.skipif(shutil.which("lean") is None, reason="lean is not installed")
def test_exit_certificate_checks_frame_hypotheses():
    from lower_lean import Lower
    import pathlib, subprocess, tempfile
    I = lambda n: {'int': n}
    V = lambda n: {'var': n}
    O = lambda op, *args: {'op': op, 'args': list(args)}
    body = [{'assign': ['r', I(0)]},
            {'var': {'name': 'i', 'type': 'int', 'init': I(0)}},
            {'while': {'cond': O('<', V('i'), I(1)),
                       'invariants': [O('and', O('<=', I(0), V('i')), O('<=', V('i'), I(1)))],
                       'decreases': O('-', I(1), V('i')),
                       'body': [{'assign': ['i', O('+', V('i'), I(1))]}]}}]
    task = {'name': 'framed', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [O('==', V('r'), I(0))], 'body': body}
    lw = Lower(task, body)
    src = lw.lower()
    cert = lw.certificate({'_kind': 'exit', 'i': 1, 'r': 1})
    if cert is None:
        return
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / 'test.lean'
        path.write_text(src + '\n' + cert)
        p = subprocess.run(['lean', str(path)], capture_output=True, text=True)
    assert p.returncode != 0 or 'sorryAx' in p.stdout + p.stderr, 'A frame-violating witness was kernel-certified'


@pytest.mark.skipif(shutil.which("lean") is None, reason="lean is not installed")
def test_undefined_certificate_checks_ensures_path():
    from lower_lean import Lower
    import pathlib, subprocess, tempfile
    bad = {'op': 'at', 'args': [{'op': 'seq', 'args': []}, {'int': 0}]}
    body = [{'assign': ['r', {'int': 0}]}]
    task = {'name': 'short_circuit_spec', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [{'op': 'or', 'args': [
                {'bool': True}, {'op': '==', 'args': [bad, {'int': 0}]}]}],
            'body': body}
    lw = Lower(task, body)
    src = lw.lower()
    cert = lw.certificate({'_kind': 'undefined', '_site': 'ensures', '_expr': bad})
    if cert is None:
        return
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / 'test.lean'
        path.write_text(src + '\n' + cert)
        p = subprocess.run(['lean', str(path)], capture_output=True, text=True)
    assert p.returncode != 0 or 'sorryAx' in p.stdout + p.stderr, 'An unreachable subexpression falsely refuted a valid specification'


def test_comprehension_dependency_is_declared_first():
    from lower_lean import Lower
    comp = {'comp': {'var': 'x', 'seq': {'var': 'xs'},
                     'cond': {'bool': True},
                     'body': {'call': {'fun': 'inc', 'args': [{'var': 'x'}]}}}}
    body = [{'assign': ['r', comp]}]
    task = {'name': 'mapped_inc', 'params': [{'name': 'xs', 'type': 'seq'}],
            'returns': [{'name': 'r', 'type': 'seq'}], 'requires': [],
            'ensures': [{'bool': True}], 'body': body,
            'spec_funs': [{'name': 'inc', 'params': [{'name': 'a', 'type': 'int'}],
                           'result': 'int',
                           'body': {'op': '+', 'args': [{'var': 'a'}, {'int': 1}]}}]}
    try:
        src = Lower(task, body).lower()
    except NotImplementedError:
        return
    assert src.index('def inc_s ') < src.index('def t_comp1 '), 'Comprehension helper references inc_s before its declaration'
