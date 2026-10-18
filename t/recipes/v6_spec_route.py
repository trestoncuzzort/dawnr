"""One greedy supplied-specification answer through the matched cached decoder.

Prior art: score_spec_given.ask/conversation and v6_server_route.Decoder.
https://github.com/trestoncuzzort/dawnr/blob/main/t/score_spec_given.py
No reference answer is sent to the model. A restart reuses saved requests.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sys

from v6_server_route import Decoder

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))
import score_spec_given


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generate(questions, decoder):
    names = [row['name'] for row in questions]
    if not names or len(names) != len(set(names)):
        raise ValueError('specification names must be nonempty and unique')
    answers = []
    for index, row in enumerate(questions, 1):
        text, stopped, tokens = decoder.one(
            score_spec_given.conversation(row, 's1'), 1024, 0, .95, 'spec-given')
        answers.append({'name': row['name'], 'reply': text, 'stopped': stopped,
                        'tokens': tokens, 'model': decoder.model, 'system': 's1'})
        print(f'specification {index}/{len(questions)}: {tokens} tokens, '
              f'{"stopped" if stopped else "budget reached"}', flush=True)
    return answers


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--identity', required=True)
    parser.add_argument('--questions', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    questions = [json.loads(line) for line in args.questions.read_text().splitlines() if line.strip()]
    if len(questions) != 33:
        parser.error('the registered specification panel contains exactly 33 questions')
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out/'generate.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('another specification run holds this output') from None
        sources = sorted(ENGINE.glob('*.py')) + sorted((ENGINE/'verifiers').rglob('*.py'))
        sources += [Path(__file__), Path(__file__).with_name('v6_server_route.py')]
        protocol = {'schema': 1, 'model': args.model, 'identity': args.identity,
                    'questions_sha256': digest(args.questions), 'system': 's1',
                    'max_new': 1024, 'temperature': 0, 'top_p': .95, 'attempts': 1,
                    'sources': {str(p.relative_to(ENGINE.parent)): digest(p) for p in sources}}
        path = args.out/'protocol.json'
        if path.exists() and json.loads(path.read_text()) != protocol:
            raise SystemExit('specification protocol changed; use a fresh output')
        path.write_text(json.dumps(protocol, indent=2)+'\n')
        done = args.out/'completed.json'
        if done.exists():
            receipt = json.loads(done.read_text())
            if receipt != {'protocol_sha256': digest(path),
                           'answers_sha256': digest(args.out/'answers.jsonl'), 'questions': 33}:
                raise SystemExit('completed specification evidence changed')
            return 0
        decoder = Decoder(args.endpoint, args.model, args.identity, args.out/'requests', concurrency=1)
        answers = generate(questions, decoder)
        temporary = args.out/'answers.jsonl.partial'
        temporary.write_text(''.join(json.dumps(row)+'\n' for row in answers))
        temporary.replace(args.out/'answers.jsonl')
        done.write_text(json.dumps({'protocol_sha256': digest(path),
                                   'answers_sha256': digest(args.out/'answers.jsonl'),
                                   'questions': len(answers)}, indent=2)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
