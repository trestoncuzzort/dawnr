import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Five findings of the GPT-6 Astra review of 2026-10-13, each reproduced before its fix: no capture of the result
# name, string literals untouched, another argument refused, both theorems audited once each, a fresh proof binder.


def test_result_substitution_avoids_capture():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path('t').resolve()))
    import lift_check_lean as m

    try:
        out = m._substitute_program(
            '∀ result : Nat, (f x) ≤ result', 'f', ['x'], 'result')
    except m.NoHarness:
        return
    assert out != '∀ result : Nat, result ≤ result', out


def test_program_substitution_preserves_string_literals():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path('t').resolve()))
    import lift_check_lean as m

    out = m._substitute_program(
        '(f x) = "(f x)".length', 'f', ['x'], 'result')
    assert out == 'result = "(f x)".length', out


def test_other_program_argument_is_refused():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path('t').resolve()))
    import lift_check_lean as m

    try:
        out = m._substitute_program(
            '(f x.succ) = (f x) + 1', 'f', ['x'], 'result')
    except m.NoHarness as exc:
        assert 'f' in str(exc)
        return
    raise AssertionError('Expected refusal for f x.succ; got ' + out)


def test_duplicate_audit_does_not_prove_both_obligations():
    import sys
    import subprocess
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    sys.path.insert(0, str(Path('t').resolve()))
    import lift_check_lean as m

    text = ('theorem t_eq_requires : True ↔ True := Iff.rfl\n'
            '#print axioms t_eq_requires\n'
            '#print axioms t_eq_requires\n')
    stdout = "'t_eq_requires' does not depend on any axioms\n" * 2
    completed = subprocess.CompletedProcess(['lean'], 0, stdout, '')
    with tempfile.TemporaryDirectory() as directory:
        with patch.object(m.subprocess, 'run', return_value=completed):
            result = m.run(text, Path(directory), 'duplicate')
    assert result['verdict'] != 'proved', result


def test_build_uses_a_fresh_proof_binder():
    import sys
    from pathlib import Path
    from types import SimpleNamespace as N
    from unittest.mock import patch
    sys.path.insert(0, str(Path('t').resolve()))
    import lift_check_lean as m

    integer = N(kind='int')
    h = N(name='h', src='Int', type=integer)
    result = N(name='result', src='Int', type=integer)
    fn = N(name='f', binders=[h], ret=integer, ret_src='Int',
           text='def f (h : Int) : Int := h')
    pre = N(name='f_precond', binders=[h],
            text='def f_precond (h : Int) : Prop := True')
    post = N(name='f_postcond', binders=[h, result],
             text='def f_postcond (h result : Int) : Prop := result = h')
    rendered = N(refusal=None, target='f', result_name='result', shape='pre-post',
                 file=N(defs={'f': fn, 'f_precond': pre, 'f_postcond': post}))
    task = {'params': [{'name': 'h', 'type': 'int'}],
            'returns': [{'name': 'result', 'type': 'int'}],
            'body': {}, 'ensures': [{}]}
    lower = N(binders=lambda ps: ' '.join(f'({n} : Int)' for n, _ in ps),
              pre_props=lambda: [], prop=lambda *args: 'result = h', types={})
    source = '\n'.join([fn.text, pre.text, post.text])
    with patch.object(m.lift_lean, 'render', return_value=rendered), \
         patch.object(m.lower_lean, 'Lower', return_value=lower):
        text, _ = m.build(source, task)
    assert '(result : Int) (h : f_precond h)' not in text
