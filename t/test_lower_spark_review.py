import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Nine findings of the GPT-6 Astra review of 2026-10-13, each reproduced before its fix (see the commit).


def test_unused_division_keeps_its_obligation():
    import lower_spark as ls
    bad = {'op': 'div', 'args': [{'int': 1}, {'int': 0}]}
    body = [
        {'var': {'name': 'scratch', 'type': 'int', 'init': bad}},
        {'assign': ['r', {'int': 0}]},
    ]
    task = {'t': 1, 'name': 'dead_partial_probe', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [{'op': '==', 'args': [{'var': 'r'}, {'int': 0}]}],
            'body': body}
    try:
        text = ls.lower(task, body)
    except NotImplementedError:
        return
    assert "T_Div (Big_Integer'(1), Big_Integer'(0))" in text


def test_early_return_does_not_erase_lemma_precondition():
    import lower_spark as ls
    lemma = {'name': 'need_pos', 'params': [{'name': 'k', 'type': 'int'}],
             'requires': [{'op': '>', 'args': [{'var': 'k'}, {'int': 0}]}],
             'ensures': [{'bool': True}], 'body': []}
    body = [{'lemma': {'name': 'need_pos', 'args': [{'int': 0}]}},
            {'return': ['r', {'int': 0}]}]
    task = {'t': 1, 'name': 'lemma_exit_probe', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [{'op': '==', 'args': [{'var': 'r'}, {'int': 0}]}],
            'lemmas': [lemma], 'body': body}
    try:
        text = ls.lower(task, body)
    except NotImplementedError:
        return
    assert "Need_pos (Big_Integer'(0))" in text


def test_certificate_rejects_unrelated_ensures_expression():
    import lower_spark as ls
    body = [{'assign': ['r', {'int': 0}]}]
    task = {'name': 'correct_zero', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [{'op': '==', 'args': [{'var': 'r'}, {'int': 0}]}],
            'body': body}
    witness = {'_kind': 'undefined', '_site': 'ensures',
               '_expr': {'op': 'div', 'args': [{'int': 1}, {'int': 0}]}}
    assert ls.certificate(task, body, witness, ls.Lower(task)) == ''


def test_undefinedness_replay_stops_at_return():
    import lower_spark as ls
    body = [
        {'if': {'cond': {'bool': True},
                'then': [{'return': ['r', {'int': 0}]}], 'else': []}},
        {'assign': ['r', {'op': 'div', 'args': [{'int': 1}, {'int': 0}]}]},
    ]
    task = {'t': 1, 'name': 'return_replay_probe', 'params': [],
            'returns': [{'name': 'r', 'type': 'int'}], 'requires': [],
            'ensures': [{'bool': True}], 'body': body}
    assert ls._undef_obligation(task, body, {}, {}, ls.Lower(task)) is None


def test_transient_fill_declares_sequence_package():
    import lower_spark as ls
    body = [{'assign': ['r', {'op': 'len', 'args': [
        {'op': 'fill', 'args': [{'var': 'n'}, {'int': 0}]}]}]}]
    task = {'t': 1, 'name': 'transient_fill_probe',
            'params': [{'name': 'n', 'type': 'int'}],
            'returns': [{'name': 'r', 'type': 'int'}],
            'requires': [{'op': '>=', 'args': [{'var': 'n'}, {'int': 0}]}],
            'ensures': [{'op': '==', 'args': [{'var': 'r'}, {'var': 'n'}]}],
            'body': body}
    text = ls.lower(task, body)
    assert 'package Seqs is new' in text


def test_join_emits_nested_slice_equality_dependency():
    import lower_spark as ls
    body = [{'assign': ['r', {'op': 'join',
                            'args': [{'var': 'm'}, {'var': 'sep'}]}]}]
    task = {'t': 1, 'name': 'join_dependency_probe',
            'params': [{'name': 'm', 'type': {'seq': 'seq'}},
                       {'name': 'sep', 'type': 'seq'}],
            'returns': [{'name': 'r', 'type': 'seq'}],
            'requires': [], 'ensures': [{'bool': True}], 'body': body}
    text = ls.lower(task, body)
    assert 'function T_Eq (S, T : Seq)' in text


def test_float_extrema_use_float_attributes():
    import lower_spark as ls
    task = {'name': 'float_extrema_probe',
            'params': [{'name': 'x', 'type': 'float'},
                       {'name': 'y', 'type': 'float'}],
            'returns': [{'name': 'r', 'type': 'float'}]}
    for op in ('min', 'max'):
        text = ls.Lower(task).expr(
            {'op': op, 'args': [{'var': 'x'}, {'var': 'y'}]},
            {'x': 'X', 'y': 'Y'}, {'x': 'float', 'y': 'float'})
        assert text == f"Long_Float'{op.capitalize()} (X, Y)"


def test_datatype_result_can_remain_unassigned_across_loop():
    import lower_spark as ls
    i = {'var': 'i'}
    body = [
        {'var': {'name': 'i', 'type': 'int', 'init': {'int': 0}}},
        {'while': {
            'cond': {'op': '<', 'args': [i, {'int': 1}]},
            'invariants': [],
            'decreases': {'op': '-', 'args': [{'int': 1}, i]},
            'body': [{'assign': ['i', {'op': '+', 'args': [i, {'int': 1}]}]}]}},
        {'assign': ['r', {'ctor': {'dtype': 'Unit', 'name': 'Only', 'args': []}}]},
    ]
    task = {'t': 1, 'name': 'datatype_loop_probe', 'params': [],
            'datatypes': [{'name': 'Unit', 'ctors': [{'name': 'Only', 'fields': []}]}],
            'returns': [{'name': 'r', 'type': {'datatype': 'Unit'}}],
            'requires': [], 'ensures': [{'bool': True}], 'body': body}
    try:
        ls.lower(task, body)
    except NotImplementedError as exc:
        assert 'datatype' in str(exc).lower()


def test_nested_empty_literal_in_conditional_keeps_expected_type():
    import lower_spark as ls
    nested = {'seq': 'seq'}
    task = {'name': 'nested_empty_branch_probe', 'params': [],
            'returns': [{'name': 'r', 'type': nested}]}
    expr = {'ite': {'cond': {'var': 'b'},
                    'then': {'op': 'seq', 'args': []},
                    'else': {'var': 'm'}}}
    text = ls.Lower(task).expr(expr, {'b': 'B', 'm': 'M'},
                               {'b': 'bool', 'm': nested}, expect=nested)
    assert 'Rows.Empty_Sequence' in text
    assert 'Seqs.Empty_Sequence' not in text
