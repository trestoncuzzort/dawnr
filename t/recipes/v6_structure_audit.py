"""Audit positive training targets and diagnose cached development structure errors.

No model generation, program execution, row mutation or evaluation-score update.
Reuses the exact structural gate in spec_first.accept and student_loop.
Sources: https://github.com/trestoncuzzort/dawnr/blob/main/t/spec_first.py
https://github.com/trestoncuzzort/dawnr/blob/main/t/student_rows.py
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))
import fuzz_lower
import spec_experiment as se
import spec_given
import student_rows
import surface


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def structural_errors(task):
    errors = fuzz_lower.check_wf(task)
    promoted = False
    if errors and task.get('t') == 0 and not fuzz_lower.check_wf(dict(task, t=1)):
        errors, promoted = [], True
    return errors, promoted


def training(path):
    rows = [json.loads(line) for line in path.read_text().split('\n') if line.strip()]
    programs, unparsed, without_t = {}, [], 0
    for index, row in enumerate(rows):
        block = se.find_block(row['chosen'])
        if block is None:
            without_t += 1
            continue
        try:
            task = surface.parse(block)
        except Exception as error:
            unparsed.append({'row': index, 'error': str(error)})
            continue
        key = hashlib.sha256(student_rows._normalised(task, body=True).encode()).hexdigest()
        if key not in programs:
            errors, promoted = structural_errors(task)
            programs[key] = {'program_sha256': key, 'has_body': bool(task.get('body')),
                'errors': errors, 'header_promotion': promoted, 'source_rows': []}
        programs[key]['source_rows'].append(index)
    body = [r for r in programs.values() if r['has_body']]
    specifications = [r for r in programs.values() if not r['has_body']]
    invalid = [r for r in body if r['errors']]
    return {'dataset_sha256': digest(path), 'rows': len(rows), 'without_t': without_t,
        'unparsed_chosen': unparsed, 'distinct_nonempty_programs': len(body),
        'invalid_nonempty_programs': invalid,
        'nonempty_header_promotions': sum(r['header_promotion'] for r in body),
        'distinct_empty_body_specifications': len(specifications),
        'empty_body_specifications_with_checker_errors': sum(bool(r['errors']) for r in specifications),
        'W1_holds': not unparsed and not invalid,
        'scope': 'Positive chosen targets only. Empty-body specifications are reported separately; no executable proof is claimed for them.'}


def forward_helper_calls(task):
    helpers = task.get('spec_funs', [])
    order = {helper['name']: index for index, helper in enumerate(helpers)}

    def calls(value):
        if isinstance(value, dict):
            call = value.get('call')
            if isinstance(call, dict) and isinstance(call.get('fun'), str):
                yield call['fun']
            for child in value.values():
                yield from calls(child)
        elif isinstance(value, list):
            for child in value:
                yield from calls(child)

    return sorted({(helper['name'], name) for index, helper in enumerate(helpers)
                   for name in calls(helper) if order.get(name, -1) > index})


def development(root, arm):
    directory = root / ('v5-dev' if arm == 'v5' else f'v6-20261018-{arm}-dev') / 'requests'
    findings = []
    for path in sorted(directory.glob('*.json')):
        if len(path.stem) != 64:
            continue
        record = json.loads(path.read_text())
        prompt = record['request']['messages'][-1]['content']
        if not prompt.startswith('Complete this t task. Keep its header'):
            continue
        spec = surface.parse(se.find_block(prompt))
        text = record['response']['choices'][0]['message']['content']
        item = {'request_sha256': path.stem, 'name': spec['name'], 'errors': []}
        block = se.find_block(text)
        if block is None:
            item['category'] = 'no task block'
        else:
            try:
                task = surface.parse(block)
            except Exception as error:
                item.update(category='parse', errors=[str(error)])
            else:
                changed = spec_given.kept(spec, task)
                if changed is not None:
                    item.update(category='specification changed', errors=[changed])
                else:
                    errors, _ = structural_errors(task)
                    item.update(category='not well formed' if errors else 'passes structural gates', errors=errors)
        if item['category'] == 'not well formed':
            errors, _ = structural_errors(spec)
            item['given_spec_errors'] = [e for e in errors if not e.startswith('task decreases without a self-call')]
            item['forward_helper_calls'] = forward_helper_calls(spec)
        findings.append(item)
    assert findings, 'missing preserved development requests'
    bad = [r for r in findings if r['category'] == 'not well formed']
    return {'cached_body_requests': len(findings), 'categories': dict(Counter(r['category'] for r in findings)),
        'invalid_body_replies_with_errors_in_given_spec': sum(bool(r['given_spec_errors']) for r in bad),
        'invalid_body_replies_with_forward_helper_calls': sum(bool(r['forward_helper_calls']) for r in bad),
        'first_error_per_invalid_reply': dict(Counter(r['errors'][0] for r in bad)),
        'invalid_body_replies': bad,
        'scope': 'Every cached body request, including replies ignored after another answer in its batch was accepted. Static diagnosis only; these are not official evaluation scores.'}


def compare_snapshots(previous, current):
    before = (previous / 'training-rows.jsonl').read_text().split('\n')
    after = (current / 'training-rows.jsonl').read_text().split('\n')
    before, after = [r for r in before if r.strip()], [r for r in after if r.strip()]
    old_lineage = json.loads((previous / 'lineage.json').read_text())
    new_lineage = json.loads((current / 'lineage.json').read_text())
    for rows, lineage in ((before, old_lineage), (after, new_lineage)):
        assert {r['row'] for r in lineage} == set(range(len(rows)))
        assert len({r['parent_row'] for r in lineage}) == len(rows)
    original_rows = {r['parent_row']: before[r['row']] for r in old_lineage}
    assert all(after[r['row']] == original_rows[r['parent_row']] for r in new_lineage)
    removed = sorted(set(original_rows) - {r['parent_row'] for r in new_lineage})
    build = json.loads((current / 'build.json').read_text())
    assert digest(current / 'training-rows.jsonl') == build['files']['training-rows.jsonl']
    return {'previous_dataset_sha256': digest(previous / 'training-rows.jsonl'),
        'new_untrained_dataset_sha256': digest(current / 'training-rows.jsonl'),
        'previous_rows': len(before), 'new_rows': len(after), 'removed_parent_rows': removed,
        'every_retained_row_byte_identical': True,
        'changed_rows_retained': build['changed_row_count'],
        'judge_python_rows_retained': build['judge_python_rows_unchanged'],
        'L1_holds': removed == [3201, 3209, 3215] and len(after) == 4086
            and build['quarantined_row_count'] == 103 and build['changed_row_count'] == 41
            and build['judge_python_rows_unchanged'] == 909,
        'scope': 'A separate untrained snapshot. The active trial keeps its registered 4089-row input.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('t/out/v6-20261018'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    evaluator = json.loads((args.root / 'proof-results/v5-dev-full/evaluator.json').read_text())
    sources = {str(p.relative_to(ENGINE.parent)): digest(p) for p in
               [ENGINE / name for name in ('surface.py', 'fuzz_lower.py', 'check_wf.py', 'spec_given.py', 'student_rows.py')]}
    assert all(evaluator[name] == value for name, value in sources.items()), 'structural checker changed'
    result = {'script': 't/recipes/v6_structure_audit.py', 'script_sha256': digest(__file__),
        'frozen_sources': sources,
        'training': {'original': training(args.root / 'training-rows.jsonl'),
                     'corrected': training(args.root / 'corrected-data-v2/training-rows.jsonl')},
        'development_cache': {arm: development(args.root, arm) for arm in ('v5', 'step400', 'final', 'average')},
        'limits': 'Well-formedness does not establish correctness or proof. This diagnostic changes no training row, model, prompt, native gate, or official evaluation result.'}
    if (args.root / 'corrected-data-lineage/build.json').is_file():
        result['lineage_correction'] = compare_snapshots(args.root / 'corrected-data-v2', args.root / 'corrected-data-lineage')
        result['training']['lineage_corrected_untrained'] = training(args.root / 'corrected-data-lineage/training-rows.jsonl')
    if args.out.exists():
        raise ValueError('preserve previous results; choose a fresh output path')
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'training': {name:{k:v for k,v in r.items() if k not in ('invalid_nonempty_programs', 'scope')}
                                 for name,r in result['training'].items()}}))


if __name__ == '__main__':
    main()
