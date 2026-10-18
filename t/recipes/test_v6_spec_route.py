"""The supplied-spec route must never transmit its reference answer."""
import sys
from pathlib import Path
import json

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import v6_spec_route as route


def test_only_question_messages_are_sent_once_with_the_frozen_budget():
    calls = []
    class Decoder:
        model = 'test'
        def one(self, *args):
            calls.append(args)
            return 'partial', False, 1024
    prompt = [{'role': 'system', 'content': 'language'}, {'role': 'user', 'content': 'contract'}]
    result = route.generate([{'name': 'example', 'prompt': prompt, 'chosen': 'SECRET REFERENCE'}], Decoder())
    assert calls == [(prompt, 1024, 0, .95, 'spec-given')]
    assert result[0]['stopped'] is False and result[0]['tokens'] == 1024
    assert 'SECRET REFERENCE' not in repr(calls)


def test_duplicate_questions_are_refused_before_any_generation():
    with pytest.raises(ValueError, match='unique'):
        route.generate([{'name': 'same'}, {'name': 'same'}], None)


def test_completed_run_is_reused_but_changed_evidence_is_refused(tmp_path, monkeypatch):
    calls = []
    class Decoder:
        model = 'test'
        def __init__(self, *_args, **_kwargs):
            pass
        def one(self, *_args):
            calls.append(1)
            return 'answer', True, 1
    monkeypatch.setattr(route, 'Decoder', Decoder)
    questions = tmp_path/'questions.jsonl'
    questions.write_text(''.join(json.dumps({'name': str(i), 'prompt': [{'role': 'user', 'content': str(i)}]})+'\n'
                                 for i in range(33)))
    output = tmp_path/'output'
    args = ['--endpoint', 'unused', '--model', 'test', '--identity', 'fixed',
            '--questions', str(questions), '--out', str(output)]
    assert route.main(args) == route.main(args) == 0 and len(calls) == 33
    (output/'answers.jsonl').write_text('changed\n')
    with pytest.raises(SystemExit, match='evidence changed'):
        route.main(args)
