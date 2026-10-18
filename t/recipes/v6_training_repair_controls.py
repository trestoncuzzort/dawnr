"""Build and check two preregistered training-contract repairs without changing training rows.

Prior art: the repository's spec_refine.check and spec_strength audit.
Source: https://github.com/trestoncuzzort/dawnr/blob/main/t/spec_refine.py
Native original/strengthened comparisons run separately over the emitted tasks.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import signal
import sys

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))
import spec_experiment as se
import spec_refine
import surface
import check_wf

ROWS_SHA256 = 'e14f766f06299d589d9a6e3293f6bf3e3f06ffac026433e2fdeff1c04294af80'
CONTROLS = [
    (69, 378, 'move_first', 'len(r) == len(s)'),
    (187, 202503, 'findLUSlength', 's1 != s2 ==> (r >= len(s1) and r >= len(s2))'),
]


def check_bounded(task, extra):
    def timeout(_signum, _frame):
        raise TimeoutError('interpreter control exceeded 60 seconds')
    previous = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(60)
    try:
        return spec_refine.check(task, extra)
    except TimeoutError:
        return {'status': 'timeout', 'accepted': False, 'real_ok': None}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw = args.rows.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ROWS_SHA256
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    assert len(rows) == 4189
    if args.out.exists():
        parser.error('preserve earlier controls; use a fresh output directory')
    tasks = args.out / 'tasks'
    tasks.mkdir(parents=True)
    protocol = {'dataset_sha256': ROWS_SHA256, 'rows_unchanged': True,
                'seconds_per_interpreter_check': 60, 'controls': [],
                'scope': 'Interpreter controls and native-proof inputs only. No training admission or model changes.'}
    for index, task_id, name, expression in CONTROLS:
        row = rows[index]
        assert row['task_id'] == task_id
        task = surface.parse(se.find_block(row['chosen']))
        assert task['name'] == name
        assert task['returns'][0]['name'] == 'r', 'repair must refer to the actual result variable'
        extra = surface.parse_expr(expression)
        modified = spec_refine.strengthen(task, extra)
        assert not check_wf.check_wf(task), 'original control is not well formed'
        assert not check_wf.check_wf(modified), 'strengthening is not well formed'
        assert modified['body'] == task['body'] and modified.get('requires') == task.get('requires')
        files = {}
        for arm, value in [('original', task), ('strengthened', modified)]:
            value = copy.deepcopy(value)
            value['name'] = name + '_' + arm
            path = tasks / (value['name'] + '.json')
            path.write_text(json.dumps(value, sort_keys=True) + '\n')
            files[arm] = {'name': value['name'], 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        protocol['controls'].append({'source_row': index, 'task_id': task_id, 'name': name,
            'expression': expression, 'chosen_sha256': hashlib.sha256(row['chosen'].encode()).hexdigest(),
            'files': files})
    (args.out / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
    results = []
    for control in protocol['controls']:
        task = surface.parse(se.find_block(rows[control['source_row']]['chosen']))
        positive = check_bounded(task, surface.parse_expr(control['expression']))
        negative = check_bounded(task, surface.parse_expr('false'))
        passed = positive.get('accepted') is True and positive.get('survivors_after') == 0
        passed = passed and negative.get('accepted') is False and negative.get('real_ok') is False
        result = {'name': control['name'], 'positive': positive, 'negative_false_clause': negative,
                  'R1_holds': passed}
        results.append(result)
        (args.out / 'interpreter.json').write_text(json.dumps(results, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    assert hashlib.sha256(args.rows.read_bytes()).hexdigest() == ROWS_SHA256
    return 0 if all(r['R1_holds'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
