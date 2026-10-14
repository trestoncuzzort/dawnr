import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Nine findings of the GPT-6 Astra review of 2026-10-13 on the rewrite stage, each reproduced before its fix: a parallel assignment reads its index expressions before any write; a block's declarations end with the block; two callees that fold to one task name are refused by name; substitution stops at a binder of the same name; a for loop's lower bound is read once when the body assigns a name it mentions; an uninitialised tuple local takes a pair default; a nested-sequence alias keeps its nesting; a local initialised by a spec function takes the function's result type; spec functions see the closure's predicates.


def test_parallel_assignment_snapshots_indices():
    import lift_parse
    import lift_rewrite as rw
    src = 'method M(a: array<int>) requires a.Length >= 2 modifies a { var i := 0; i, a[i] := 1, 9; }'
    m = lift_parse.parse(src).decls[0]
    scope = rw.Scope(renames={'i': 'i', 'a': 'a'}, types={'i': 'int', 'a': 'seq'})
    record = rw.LiftRecord(source_path='x.dfy', method='M', rprint_sha256='')
    out = rw._lift_stmt(m.body[1], scope, {}, 'M', 'x__m', rw._Renamer(), record)
    env = {'i': 0, 'a': [4, 5]}
    def evaluate(e):
        if 'int' in e:
            return e['int']
        if 'var' in e:
            return env[e['var']]
        assert e['op'] == 'update'
        seq, index, value = [evaluate(a) for a in e['args']]
        result = list(seq)
        result[index] = value
        return result
    for stmt in out:
        if 'var' in stmt:
            decl = stmt['var']
            env[decl['name']] = evaluate(decl['init'])
        else:
            name, value = stmt['assign']
            env[name] = evaluate(value)
    assert env['a'] == [9, 5]


def test_block_shadow_does_not_escape():
    import lift_parse
    import lift_rewrite as rw
    m = lift_parse.parse('method M() returns (r: int) { var x := 1; { var x := 2; } r := x; }').decls[0]
    scope = rw.Scope(renames={'r': 'r'}, types={'r': 'int'}, ret_name='r')
    record = rw.LiftRecord(source_path='x.dfy', method='M', rprint_sha256='')
    renamer = rw._Renamer()
    def lift(stmt):
        return rw._lift_stmt(stmt, scope, {}, 'M', 'x__m', renamer, record)
    outer_name = lift(m.body[0])[0]['var']['name']
    lift(m.body[1])
    final_assignment = lift(m.body[2])[0]
    assert final_assignment['assign'][1] == {'var': outer_name}


def test_case_distinct_callees_are_not_merged():
    from types import SimpleNamespace
    import lift_parse
    import lift_rewrite as rw
    src = ('method Foo() returns (x: int) { x := 1; } '
           'method foo() returns (x: int) { x := 2; } '
           'method Caller() returns (r: int) ensures r == 3 '
           '{ var a := Foo(); var b := foo(); r := a + b; }')
    module = lift_parse.parse(src)
    methods = {d.name: d for d in module.decls if isinstance(d, rw.MethodDecl)}
    def plan(name, callees=()):
        return SimpleNamespace(method=methods[name], closure=(), pair_returns=None,
                               rewrites=(), callees=callees)
    caller = plan('Caller', (('Foo', plan('Foo')), ('foo', plan('foo'))))
    result = rw.rewrite(module, caller, 'case.dfy', '')
    assert result.refusal is not None or len(result.task['methods']) == 2


def test_substitution_respects_quantifier_shadowing():
    import lift_parse
    import lift_rewrite as rw
    src = 'method M() returns (r: bool) { r := forall x: int | 0 <= x < 1 :: x == 1; }'
    q = lift_parse.parse(src).decls[0].body[0].values[0]
    replacement = rw.IntLit(line=q.line, value=7)
    assert rw._subst(q, 'x', replacement) == q


def test_for_lower_bound_is_frozen():
    import lift_parse
    import lift_rewrite as rw
    src = ('method M() returns (r: int) { var lower := 0; r := 0; '
           'for i := lower to 3 { lower := lower + 2; r := r + 1; } }')
    m = lift_parse.parse(src).decls[0]
    scope = rw.Scope(renames={'lower': 'lower', 'r': 'r'}, types={'lower': 'int', 'r': 'int'})
    record = rw.LiftRecord(source_path='x.dfy', method='M', rprint_sha256='')
    out = rw._lift_stmt(m.body[2], scope, {}, 'M', 'x__m', rw._Renamer(), record)
    env = {'lower': 0, 'r': 0}
    def evaluate(e):
        if 'int' in e:
            return e['int']
        if 'var' in e:
            return env[e['var']]
        a, b = [evaluate(x) for x in e['args']]
        if e['op'] == '+':
            return a + b
        assert e['op'] == '<='
        return a <= b
    for stmt in out[:-1]:
        decl = stmt['var']
        env[decl['name']] = evaluate(decl['init'])
    loop = out[-1]['while']
    for stmt in loop['body']:
        name, value = stmt['assign']
        env[name] = evaluate(value)
    assert all(evaluate(inv) for inv in loop['invariants'])


def test_tuple_local_has_tuple_default():
    import lift_parse
    import lift_rewrite as rw
    src = 'method M() returns (r: int) { var p: (int, bool); p := (1, true); r := p.0; }'
    stmt = lift_parse.parse(src).decls[0].body[0]
    record = rw.LiftRecord(source_path='x.dfy', method='M', rprint_sha256='')
    out = rw._lift_stmt(stmt, rw.Scope(), {}, 'M', 'x__m', rw._Renamer(), record)
    decl = out[0]['var']
    assert decl['init'] == rw._type_default(decl['type'])


def test_nested_sequence_alias_preserves_type():
    from types import SimpleNamespace
    import lift_parse
    import lift_rewrite as rw
    src = 'method M(m: seq<seq<int>>) returns (r: seq<seq<int>>) { var x := m; r := x; }'
    module = lift_parse.parse(src)
    plan = SimpleNamespace(method=module.decls[0], closure=(), pair_returns=None,
                           rewrites=(), callees=())
    result = rw.rewrite(module, plan, 'nested.dfy', '')
    assert result.task['body'][0]['var']['type'] == {'seq': 'seq'}


def test_spec_function_result_drives_local_type():
    from types import SimpleNamespace
    import lift_parse
    import lift_rewrite as rw
    src = ('function MakeSeq(): seq<int> { [1] } '
           'method M() returns (r: seq<int>) { var x := MakeSeq(); r := x; }')
    module = lift_parse.parse(src)
    function = next(d for d in module.decls if isinstance(d, rw.FunctionDecl))
    method = next(d for d in module.decls if isinstance(d, rw.MethodDecl))
    plan = SimpleNamespace(method=method, closure=(function,), pair_returns=None,
                           rewrites=(), callees=())
    result = rw.rewrite(module, plan, 'functions.dfy', '')
    assert result.task['body'][0]['var']['type'] == 'seq'


def test_spec_function_quantifier_can_use_predicate_bounds():
    from types import SimpleNamespace
    import lift_parse
    import lift_rewrite as rw
    src = ('predicate B(i: int, n: int) { 0 <= i < n } '
           'predicate All(n: int) { forall i: int | B(i, n) :: i >= 0 } '
           'method M(n: int) returns (r: int) ensures All(n) { r := 0; }')
    module = lift_parse.parse(src)
    functions = tuple(d for d in module.decls if isinstance(d, rw.FunctionDecl))
    method = next(d for d in module.decls if isinstance(d, rw.MethodDecl))
    plan = SimpleNamespace(method=method, closure=functions, pair_returns=None,
                           rewrites=(), callees=())
    result = rw.rewrite(module, plan, 'bounds.dfy', '')
    assert result.refusal is None
    assert len(result.task['spec_funs']) == 2
