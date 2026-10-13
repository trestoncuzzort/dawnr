import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ten findings of the review on surface, each reproduced before its fix: a declared function or lemma named like a call notation (abs, old, assert) is refused by the printer; a range loop's lower bound that the body assigns is read once at entry; a comprehension's display or comprehension source is parenthesised; a declared constructor wins over a string member of the same name; an array write makes the array an assigned name for the fixed-bound check; a projection on an integer literal keeps its parentheses; toreal, floor and ceil have arities; a zero denominator is refused.


def test_shadowed_builtin_preserves_specification():
    import surface as s
    task = s.parse('t 1 task probe() returns (r: int) ensures abs(-1) == 0 spec fun abs(x: int): int = 0 { r := 0; }')
    task['ensures'][0]['args'][0] = {'op': 'abs', 'args': [{'int': -1}]}
    try:
        text = s.print_task(task)
    except s.SurfaceError:
        return
    assert s.parse(text) == task


def test_range_lower_bound_is_not_reevaluated_in_invariant():
    import sys
    import operator
    sys.path.insert(0, 't')
    import surface as s
    task = s.parse('t 1 task probe() returns (r: int) ensures r == 1 { var lo: int := 0; r := 0; for i in [lo, 1) invariant r == i { lo := 10; r := r + 1; } }')
    env = {}
    ops = {'+': operator.add, '-': operator.sub, '<': operator.lt, '<=': operator.le, '==': operator.eq}
    def value(e):
        if 'int' in e:
            return e['int']
        if 'bool' in e:
            return e['bool']
        if 'var' in e:
            return env[e['var']]
        return ops[e['op']](*(value(a) for a in e['args']))
    def execute(st):
        if 'var' in st:
            v = st['var']
            env[v['name']] = value(v['init'])
        else:
            name, rhs = st['assign']
            env[name] = value(rhs)
    for st in task['body']:
        if 'while' not in st:
            execute(st)
            continue
        w = st['while']
        assert value(w['cond'])
        for step in w['body']:
            execute(step)
        assert all(value(inv) for inv in w['invariants']), env


def test_assert_lemma_call_round_trip():
    import surface as s
    task = s.parse('t 1 task probe() returns (r: int) ensures r == 0 lemma assert(x: bool) requires false ensures false { } { r := 0; }')
    task['body'].append({'lemma': {'name': 'assert', 'args': [{'bool': True}]}})
    try:
        text = s.print_task(task)
    except s.SurfaceError:
        return
    assert s.parse(text) == task


def test_old_function_call_round_trip():
    import surface as s
    task = s.parse('t 1 task probe() returns (r: int) ensures old(0) == 0 spec fun old(x: int): int = 1 { r := 0; }')
    task['ensures'][0]['args'][0] = {'call': {'fun': 'old', 'args': [{'int': 0}]}}
    try:
        text = s.print_task(task)
    except s.SurfaceError:
        return
    assert s.parse(text) == task


def test_comprehension_sources_round_trip():
    import surface as s
    for text in ('[x for x in ([])]', '[x for x in ([y for y in s])]'):
        expr = s.parse_expr(text)
        assert s.parse_expr(s.pexpr(expr)) == expr


def test_constructor_named_like_string_member():
    import surface as s
    task = s.parse('datatype Case = lower | upper\nt 1 task choose() returns (r: Case) { r := Case.lower; }')
    assert task['body'][0]['assign'][1] == {'ctor': {'dtype': 'Case', 'name': 'lower', 'args': []}}


def test_array_write_cannot_mutate_for_bound():
    import sys
    import unittest
    sys.path.insert(0, 't')
    import surface as s
    text = 't 1 task grow(a: array) returns (r: int) modifies a requires len(a) > 0 { r := 0; for i in [0, a[0]) { a[0] := a[0] + 1; } }'
    with unittest.TestCase().assertRaises(s.SurfaceError):
        s.parse(text)


def test_integer_receiver_projection_round_trip():
    import surface as s
    expr = s.parse_expr('(1).0')
    assert s.parse_expr(s.pexpr(expr)) == expr


def test_floor_rejects_extra_argument():
    import sys
    import unittest
    sys.path.insert(0, 't')
    import surface as s
    expr = {'op': 'floor', 'args': [{'rat': [1, 2]}, {'int': 99}]}
    with unittest.TestCase().assertRaises(s.SurfaceError):
        s.pexpr(expr)


def test_zero_denominator_is_refused_without_hanging():
    import subprocess
    import sys
    code = "import surface\ntry:\n    surface.pexpr({'rat': [1, 0]})\nexcept surface.SurfaceError:\n    pass\nelse:\n    raise AssertionError('zero denominator accepted')\n"
    subprocess.run([sys.executable, '-c', code], cwd=str(Path(__file__).resolve().parent), timeout=5, check=True)
