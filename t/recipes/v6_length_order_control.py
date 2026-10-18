"""Build the preregistered length-ordered contract control from the preserved training row.

Reuses v6_training_repair_controls.check_bounded and spec_refine.strengthen.
Source: https://github.com/trestoncuzzort/dawnr/blob/main/t/spec_refine.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_wf
import spec_experiment as se
import spec_refine
import surface
from v6_training_repair_controls import ROWS_SHA256, check_bounded

CLAUSES = [
    'len(s1) > len(s2) ==> r == len(s1)',
    'len(s2) > len(s1) ==> r == len(s2)',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw = args.rows.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ROWS_SHA256
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    assert len(rows) == 4189
    row = rows[187]
    assert row['task_id'] == 202503
    task = surface.parse(se.find_block(row['chosen']))
    assert task['name'] == 'findLUSlength' and task['returns'][0]['name'] == 'r'
    extra = [surface.parse_expr(clause) for clause in CLAUSES]
    modified = spec_refine.strengthen(task, extra)
    assert not check_wf.check_wf(task) and not check_wf.check_wf(modified)
    assert modified['body'] == task['body'] and modified['requires'] == task['requires']
    if args.out.exists():
        parser.error('use a fresh output directory and preserve previous controls')
    (args.out / 'tasks').mkdir(parents=True)
    native = {**modified, 'name': 'findLUSlength_length_order'}
    path = args.out / 'tasks/findLUSlength_length_order.json'
    path.write_text(json.dumps(native, sort_keys=True) + '\n')
    protocol = {'dataset_sha256': ROWS_SHA256, 'source_row': 187, 'task_id': 202503,
        'chosen_sha256': hashlib.sha256(row['chosen'].encode()).hexdigest(),
        'clauses': CLAUSES, 'body_and_preconditions_unchanged': True,
        'task_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'original_kernel_table_sha256': 'e9f62d621813fa360259bb1e6a749750a92649d3271ecc406f3fa24f69f1cd6d',
        'original_passing_kernels': 6, 'seconds_per_interpreter_check': 60,
        'scope': 'Single training-data control. No training admission or model/evaluation change.'}
    (args.out / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
    positive = check_bounded(task, extra)
    negative = check_bounded(task, surface.parse_expr('false'))
    passed = positive.get('accepted') is True and positive.get('survivors_after') == 0
    passed = passed and negative.get('accepted') is False and negative.get('real_ok') is False
    result = {'positive': positive, 'negative_false_clause': negative, 'R3_interpreter_holds': passed}
    (args.out / 'interpreter.json').write_text(json.dumps(result, indent=2) + '\n')
    assert hashlib.sha256(args.rows.read_bytes()).hexdigest() == ROWS_SHA256
    print(json.dumps(result), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
