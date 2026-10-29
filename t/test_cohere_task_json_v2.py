"""The internal teacher's named operands preserve contracts and reject malformed trees."""
import json
from pathlib import Path
import sys

import pytest
pytest.importorskip("jsonschema")
from jsonschema import Draft202012Validator, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))
import cohere_json_smoke as smoke
import cohere_proxy as proxy
import cohere_task_json as v1
import cohere_task_json_v2 as v2
from test_cohere_task_json import body, conversations, provider, task


@pytest.mark.parametrize("source", [
    smoke.SYNTHETIC,
    't 1 task folded(s: seq) returns (r: int) ensures r == fold((a, x) => a + x, 0, s) {}',
    't 1 task filtered(s: seq) returns (r: seq) ensures r == [x for x in s if x > 0] {}',
    't 1 task nested(s: seq<seq>) returns (r: (int, seq)) ensures r == (len(s), []) {}',
    't 1 task minimum(a: int, b: int) returns (r: int) ensures r == min(a, b) {}',
    't 1 task minimum(s: seq) returns (r: int) requires len(s) > 0 ensures r == min(s) {}',
])
def test_exact_roundtrip_keeps_all_clauses_and_bodies(source):
    expected = v1.surface.parse(source)
    document = v2.contract_document(expected)
    assert v2.decode_contract(json.dumps(document)) == expected
    assert v2.decode(document) == v1.contract_document(expected)


@pytest.mark.parametrize('op,count', [(op, n) for op in sorted(v1.check_wf.V1_OPS)
                                    for n in range(5) if v2.arities(op) is not None])
def test_each_operator_arity_is_a_schema_constraint(op, count):
    document = v2.contract_document(task())
    expression = {'op': op, **{f'arg{i}': {'int': i} for i in range(1, count + 1)}}
    document['ensures'] = [expression]
    valid = Draft202012Validator(v2.schema()).is_valid(document)
    native = {'op': op, 'args': [{'int': i} for i in range(1, count + 1)]}
    _, errors = v1.check_wf.expression_type(native, {}, positions={})
    engine_accepts_arity = not any(error.rule in ('op-arity', 'strlib-arity') for error in errors)
    assert valid == engine_accepts_arity


@pytest.mark.parametrize('typ', [{'seq': 'int'}, {'set': 'int'}, {'seq': {'set': 'int'}}])
def test_noncanonical_types_are_refused_without_rewriting(typ):
    document = v2.contract_document(task())
    document['params'][0]['type'] = typ
    with pytest.raises(ValidationError):
        v2.decode_contract(json.dumps(document))


def test_variable_length_arguments_and_pure_calls_are_preserved():
    expr = {'op': 'seq', 'args': [{'call': {'fun': 'f', 'args': [{'int': 1}]}},
                                {'op': '+', 'args': [{'int': 2}, {'int': 3}]}]}
    wire = v2.encode(expr)
    assert len(wire['args']) == 2
    assert wire['args'][0]['call'] == expr['args'][0]['call']
    assert wire['args'][1] == {'op': '+', 'arg1': {'int': 2}, 'arg2': {'int': 3}}
    assert v2.decode(wire) == expr


def test_same_problem_evidence_and_six_examples_with_distinct_identity():
    original = conversations()
    converted = v2.messages(original)
    assert converted[1] == original[1]
    for i in range(6):
        assert 'original example ' + str(i) in converted[0]['content']
    examples = v1.re.findall(r'```json\s*\n(.*?)```', converted[0]['content'], v1.re.DOTALL)
    assert len(examples) == 6
    for example in examples:
        v2.decode_contract(example)
    assert v2.identity().startswith('t-json-v2:') and v2.identity() != v1.identity()
    assert proxy.to_cohere(body(), 'command-a-03-2025', 0, 'json-v2')['response_format']['schema'] == v2.schema()


def test_semantic_error_is_still_refused_and_original_reply_is_retained():
    document = v2.contract_document(task())
    document['ensures'][0]['arg2'] = {'var': 'unknown'}
    raw = provider(document)
    response = proxy.structured_reply(raw, {}, 8000, 'command-a-03-2025', 'json-v2')
    assert response['choices'][0]['message']['content'] == ''
    assert response['cohere_source']['response'] == raw
    assert response['cohere_source']['representation'] == 'json-v2'
    assert response['cohere_source']['conversion']['status'] == 'refused'


def test_provider_check_exercises_v2_through_the_actual_decoder(tmp_path):
    primer = conversations()[0]['content'][len(v1.spec_first_rows.SPEC_SYSTEM + '\n\n'):]
    prepared = smoke.inputs(primer, 'json-v2')
    calls = []
    def caller(key, request, attempts, timeout):
        assert attempts == 1 and request['response_format']['schema'] == v2.schema()
        calls.append(request)
        return provider(v2.contract_document(prepared['expected']))
    result = smoke.run(tmp_path/'probe', 'unused', primer, caller, representation='json-v2')
    assert result['all_conditions_hold'] and result['representation'] == 'json-v2'
    assert len(calls) == result['requests'] == 1
