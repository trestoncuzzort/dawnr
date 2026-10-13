import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Eleven findings of the GPT-6 Astra review of 2026-10-13 on tshape, each reproduced before its fix: locals inside parallel loops are declared types; operators in methods and lemmas count; the all-shapes wildcard does not carry the library; sequence-quantifier substitution avoids capture; membership typing uses each spec function's own scope; a repeated parallel index is renamed in its body and fresh in the task; a heap task with several results is refused; the heap postcondition rewrite stops at a binder of the result's name; a method-only exit is refused; every declared result types an empty display.


def test_declared_types_in_parallel_loop():
    import tshape
    ty = {'map': ['int', 'bool']}
    body = [{'par': {'var': 'i', 'lo': {'int': 0}, 'hi': {'int': 1}, 'invariants': [], 'body': [
        {'var': {'name': 'lookup', 'type': ty, 'init': {'op': 'mapdisp', 'args': []}}}
    ]}}, {'assign': ['r', {'int': 0}]}]
    task = {'params': [], 'returns': [{'name': 'r', 'type': 'int'}]}
    assert ty in tshape.declared_types(task, body)


def test_library_operator_in_method_is_refused():
    import unittest
    import tshape
    body = [{'return': ['r', {'int': 0}]}]
    task = {
        'params': [], 'returns': [{'name': 'r', 'type': 'int'}], 'body': body,
        'methods': [{'name': 'm', 'params': [{'name': 'x', 'type': 'int'}],
                     'returns': [{'name': 'y', 'type': 'int'}],
                     'body': [{'return': ['y', {'op': 'abs', 'args': [{'var': 'x'}]}]}]}]
    }
    with unittest.TestCase().assertRaisesRegex(NotImplementedError, 'abs'):
        tshape.abstain_on_library(task, body, 'K', frozenset({'in', 'maxs'}))


def test_all_shapes_does_not_imply_all_library_operations():
    import unittest
    import tshape
    body = [{'return': ['r', {'op': 'abs', 'args': [{'var': 'x'}]}]}]
    task = {'params': [{'name': 'x', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}], 'body': body}
    with unittest.TestCase().assertRaisesRegex(NotImplementedError, 'abs'):
        tshape.abstain_unless_carried(task, body, 'K', carried={'*'}, lib=frozenset())


def test_seq_quantifier_substitution_avoids_capture():
    import tshape

    def evaluate(e, env):
        if 'int' in e:
            return e['int']
        if 'var' in e:
            return env[e['var']]
        if 'op' in e:
            a = [evaluate(v, env) for v in e['args']]
            op = e['op']
            if op == 'seq':
                return a
            if op == 'len':
                return len(a[0])
            if op == 'at':
                return a[0][a[1]]
            if op == '==':
                return a[0] == a[1]
            raise AssertionError(op)
        kind = 'forall' if 'forall' in e else 'exists'
        q = e[kind]
        values = (evaluate(q['in'], env) if 'in' in q else
                  range(evaluate(q['lo'], env), evaluate(q['hi'], env)))
        results = (evaluate(q['body'], {**env, q['var']: v}) for v in values)
        return all(results) if kind == 'forall' else any(results)

    predicate = {'forall': {'var': 'x', 'in': {'op': 'seq', 'args': [{'var': 'j'}]},
        'body': {'exists': {'var': 'j', 'lo': {'int': 0}, 'hi': {'int': 1},
            'body': {'op': '==', 'args': [{'var': 'x'}, {'var': 'r'}]}}}}}
    body = [{'return': ['r', {'int': 0}]}]
    task = {'params': [{'name': 'j', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}], 'ensures': [predicate], 'body': body}
    rewritten, _ = tshape.desugar_seq_quants(task, body)
    env = {'j': 1, 'r': 0}
    assert evaluate(predicate, env) is False
    assert evaluate(rewritten['ensures'][0], env) is False


def test_membership_uses_each_spec_functions_scope():
    import tshape
    body = [{'return': ['r', {'bool': True}]}]
    task = {
        'params': [], 'returns': [{'name': 'r', 'type': 'bool'}], 'body': body,
        'spec_funs': [
            {'name': 'f', 'params': [{'name': 'x', 'type': 'set'}],
             'result': 'bool', 'body': {'bool': True}},
            {'name': 'g', 'params': [{'name': 'x', 'type': 'seq'}],
             'result': 'bool', 'body': {'op': 'in', 'args': [{'int': 0}, {'var': 'x'}]}}
        ]
    }
    assert tshape.seq_membership_used(task, body)


def test_repeated_parallel_index_is_renamed_in_body():
    import tshape
    body = [{'par': {'var': 'i', 'lo': {'int': 0}, 'hi': {'int': 1},
                     'invariants': [], 'body': [{'aset': ['a', {'var': 'i'}, {'var': 'i'}]}]}}
            for _ in range(2)]
    task = {'params': [{'name': 'a', 'type': 'array'}],
            'returns': [{'name': 'r', 'type': 'int'}], 'body': body}
    _, lowered = tshape.desugar_par(task, body)
    second_index = lowered[2]['var']['name']
    update = lowered[3]['while']['body'][0]['aset']
    assert update[1] == {'var': second_index}
    assert update[2] == {'var': second_index}


def test_parallel_index_name_is_fresh():
    import tshape
    body = [{'par': {'var': 'i', 'lo': {'int': 0}, 'hi': {'int': 1},
                     'invariants': [], 'body': []}} for _ in range(2)]
    task = {'params': [{'name': 'i_p2', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}], 'body': body}
    _, lowered = tshape.desugar_par(task, body)
    parameter_names = {p['name'] for p in task['params']}
    generated_names = [s['var']['name'] for s in lowered if 'var' in s]
    assert parameter_names.isdisjoint(generated_names)
    assert len(generated_names) == len(set(generated_names))


def test_heap_multiple_results_are_refused():
    import unittest
    import tshape
    body = [{'assign': ['r', {'int': 0}]}, {'assign': ['s', {'int': 1}]}]
    task = {'params': [{'name': 'm', 'type': 'array'}], 'modifies': ['m'],
            'returns': [{'name': 'r', 'type': 'int'}, {'name': 's', 'type': 'int'}],
            'ensures': [], 'body': body}
    with unittest.TestCase().assertRaisesRegex(NotImplementedError, 'return|result'):
        tshape.desugar_heap(task, body)


def test_heap_postcondition_preserves_bound_result_name():
    import tshape
    body = [{'return': ['r', {'int': 0}]}]
    task = {'params': [{'name': 'm', 'type': 'array'}], 'modifies': ['m'],
            'returns': [{'name': 'r', 'type': 'int'}], 'body': body,
            'ensures': [{'forall': {'var': 'r', 'lo': {'int': 0}, 'hi': {'int': 2},
                         'body': {'op': '==', 'args': [{'var': 'r'}, {'int': 0}]}}}]}
    rewritten, _, _ = tshape.desugar_heap(task, body)
    q = rewritten['ensures'][0]['forall']
    assert q['body']['args'][0] == {'var': q['var']}


def test_method_only_exit_is_refused():
    import unittest
    import tshape
    body = [{'return': ['r', {'int': 0}]}]
    task = {'params': [], 'returns': [{'name': 'r', 'type': 'int'}], 'body': body,
            'methods': [{'name': 'm', 'params': [],
                         'returns': [{'name': 'v', 'type': 'int'}],
                         'body': [
                             {'while': {'cond': {'bool': True}, 'invariants': [],
                                        'decreases': {'int': 0}, 'body': [{'break': True}]}},
                             {'return': ['v', {'int': 0}]}
                         ]}]}
    with unittest.TestCase().assertRaisesRegex(NotImplementedError, 'method'):
        tshape.desugar_exits(task, body)


def test_empty_display_uses_second_result_type():
    import tshape
    empty = {'op': 'seq', 'args': []}
    ty = {'seq': 'bool'}
    body = [{'assign': ['r', {'int': 0}]}, {'assign': ['flags', empty]}]
    task = {'params': [],
            'returns': [{'name': 'r', 'type': 'int'}, {'name': 'flags', 'type': ty}]}
    annotations = tshape.empty_display_types(task, body)
    assert annotations.get(id(empty)) == ty
