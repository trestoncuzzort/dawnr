"""Build a separate corrected snapshot from measured training-contract evidence.

Prior art: student_rows, spec_first_rows, and the v5 full-mixture builder.
https://github.com/trestoncuzzort/dawnr/blob/main/t/student_rows.py
Original rows and every quarantined row remain available for reproduction.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))
import check_wf
import loop_filter
import spec_experiment as se
import student_rows
import surface
from v6_compare import confirmed_specification, integrity_findings
from v6_training_reference_audit import DATASET, digest

FENCE = re.compile(r'```t\s*\n(.*?)```', re.S)


def read(path):
    return [json.loads(line) for line in path.read_text().split('\n') if line.strip()]


def fingerprint(task, body=True):
    return hashlib.sha256(student_rows._normalised(task, body=body).encode()).hexdigest()


def row_key(row):
    return json.dumps([row['prompt'], row['chosen']], sort_keys=True)


def problem_id(row):
    if row.get('task_id') is not None:
        return int(row['task_id'])
    for field in ('name', 'task'):
        if isinstance(row.get(field), str):
            found = loop_filter.problem_id(row[field])
            if found is not None:
                return found
    return None


def validate_run(directory):
    assert (directory / 'COMPLETE').is_file()
    summary = json.loads((directory / 'summary.json').read_text())
    for name in ('manifest', 'runtime', 'results'):
        suffix = '.jsonl' if name == 'results' else '.json'
        assert digest(directory / (name + suffix)) == summary[name + '_sha256']
    manifest = json.loads((directory / 'manifest.json').read_text())
    assert manifest['dataset_sha256'] == DATASET
    results = read(directory / 'results.jsonl')
    assert len(results) == summary['programs'] == len(manifest['selected'])
    assert {r['program_sha256'] for r in results} == {r['program_sha256'] for r in manifest['selected']}
    for item in manifest['selected']:
        assert digest(directory / 'tasks' / (item['program_sha256'] + '.json')) == item['task_sha256']
    return manifest, results


def rewrite(row, task, repaired):
    """Change one positive target and matching supplied specifications together."""
    out = copy.deepcopy(row)
    original_contract = fingerprint(task, body=False)
    extra = repaired['ensures'][len(task['ensures']):]
    assert extra and repaired['ensures'][:len(task['ensures'])] == task['ensures']
    modified = copy.deepcopy(task)
    modified['ensures'] += extra
    if modified['body']:
        assert not check_wf.check_wf(modified)
    block = se.find_block(row['chosen'])
    assert block is not None and row['chosen'].count(block) == 1
    out['chosen'] = row['chosen'].replace(block, surface.print_task(modified).strip(), 1)
    prompt_changes = 0
    for message in out['prompt']:
        if message['role'] != 'user':
            continue
        def replace(match):
            nonlocal prompt_changes
            try:
                given = surface.parse(match.group(1))
            except (ValueError, surface.SurfaceError):
                return match.group(0)
            if given.get('body') or fingerprint(given, body=False) != original_contract:
                return match.group(0)
            given['ensures'] += copy.deepcopy(extra)
            prompt_changes += 1
            assert fingerprint(given, body=False) == fingerprint(modified, body=False)
            return '```t\n' + surface.print_task(given).strip() + '\n```'
        message['content'] = FENCE.sub(replace, message['content'])
        if 'Keep its header, parameters, requires, ensures and spec funs exactly' in message['content']:
            assert prompt_changes == 1, 'a supplied contract must change with its answer'
    return out, prompt_changes


def build(args):
    assert digest(args.rows) == DATASET
    originals = read(args.rows)
    raw_lines = [line for line in args.rows.read_text().split('\n') if line.strip()]
    assert len(originals) == len(raw_lines) == 4189
    original_manifest, original_results = validate_run(args.original_audit)
    repair_manifest, repair_results = validate_run(args.repairs)
    assert repair_manifest['kind'] == 'repaired'
    repair_results = {r['program_sha256']: r for r in repair_results}
    # Preserve the frozen scoring implementation across the original and repaired checks.
    old_runtime = json.loads((args.original_audit / 'runtime.json').read_text())
    new_runtime = json.loads((args.repairs / 'runtime.json').read_text())
    sources = lambda value: {k:v for k,v in value['sources'].items()
                            if k != 't/recipes/v6_training_reference_audit.py'}
    assert sources(old_runtime) == sources(new_runtime)
    assert old_runtime['reference_plus_sha256'] == new_runtime['reference_plus_sha256']
    native = {}
    for arm, subdir in [('initial', 'training-repair-controls-v3'),
                        ('direct', 'direct-repair-controls'), ('length-order', 'length-order-control')]:
        directory = args.native_root / subdir
        for name, expected in repair_manifest['native_controls'][arm].items():
            assert digest(directory / name) == expected
        _, cells = se.parse_kernel_table(directory / 'kernels.md')
        assert integrity_findings(cells) == {'contradictions': [], 'unsound_cells': []}
        native.update(cells)
    programs, specifications = {}, {}
    for item in repair_manifest['selected']:
        result = repair_results[item['program_sha256']]
        assert result['confirmed_reference'] and result['body_examples_all_pass']
        assert confirmed_specification(result['verdict'])
        index, = item['source_rows']
        original = surface.parse(se.find_block(originals[index]['chosen']))
        repaired = json.loads((args.repairs / 'tasks' / (item['program_sha256'] + '.json')).read_text())
        assert fingerprint(original) == item['original_program_sha256']
        assert fingerprint(repaired) == item['program_sha256']
        assert {k:v for k,v in repaired.items() if k != 'ensures'} == {
            k:v for k,v in original.items() if k != 'ensures'}
        native_name = item['name'] + ('_length_order' if item['name'] == 'findLUSlength' else '_strengthened')
        cells = native[native_name]
        passing = [k for k,v in cells.items() if v == 'verified / refuted']
        assert len(passing) == item['native_passing_kernels'] >= item['original_native_passing_kernels'] >= 1
        info = {'item': item, 'task': repaired, 'passing': passing,
                'undecided': [k for k in cells if k not in passing]}
        programs[item['original_program_sha256']] = info
        specifications[(item['task_id'], fingerprint(original, body=False))] = info

    quarantine_contracts = {}
    for result in original_results:
        if result['confirmed_reference']:
            continue
        task = json.loads((args.original_audit / 'tasks' / (result['program_sha256'] + '.json')).read_text())
        quarantine_contracts.setdefault((result['task_id'], fingerprint(task, body=False)), []).append(
            result['program_sha256'])
    output, quarantined, lineage, changed, duplicate_rows, seen = [], [], [], [], [], set()
    for index, (row, raw) in enumerate(zip(originals, raw_lines)):
        row_id = problem_id(row)
        block = se.find_block(row['chosen'])
        task = surface.parse(block) if block is not None else None
        info = None
        if task is not None:
            info = programs.get(fingerprint(task)) if task.get('body') else specifications.get(
                (row_id, fingerprint(task, body=False)))
        if info is not None:
            assert row_id == info['item']['task_id']
            updated, prompt_changes = rewrite(row, task, info['task'])
            old_proof = {k:row[k] for k in ('kernels_verified', 'undecided', 'proof') if k in row}
            executable = bool(task['body'])
            updated['kernels_verified'] = len(info['passing']) if executable else None
            updated['undecided'] = info['undecided'] if executable else None
            updated['v6_repair'] = {'parent_dataset_sha256': DATASET, 'parent_row': index,
                'parent_row_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                'original_proof_metadata': old_proof,
                'reference_manifest_sha256': digest(args.repairs / 'manifest.json'),
                'program_sha256': info['item']['program_sha256'], 'chosen_is_executable': executable,
                'supporting_program_kernels': info['passing']}
            assert surface.parse(se.find_block(updated['chosen']))['body'] == task['body']
            raw = json.dumps(updated, sort_keys=True)
            changed.append({'parent_row': index, 'task_id': row_id, 'executable': executable,
                            'supplied_specifications_updated': prompt_changes,
                            'program_sha256': info['item']['program_sha256']})
            row = updated
        elif task is not None and (row_id, fingerprint(task, body=False)) in quarantine_contracts:
            quarantined.append({'parent_row': index, 'row': row,
                'contract_program_sha256s': quarantine_contracts[(row_id, fingerprint(task, body=False))],
                'reason': 'Positive target contract did not pass the registered reference gate; this is not a claim that every body is wrong.'})
            continue
        key = row_key(row)
        if key in seen:
            duplicate_rows.append(index)
            continue
        seen.add(key)
        lineage.append({'row': len(output), 'parent_row': index, 'changed': info is not None})
        output.append(raw)
    built = [json.loads(line) for line in output]
    assert {r['program_sha256'] for r in changed} == {r['program_sha256'] for r in repair_manifest['selected']}
    assert [r for r in built if r.get('kind') == 'judge-python'] == [r for r in originals if r.get('kind') == 'judge-python']
    for path in (args.dev, args.heldout):
        assert not set(map(int, path.read_text().split())) & {problem_id(r) for r in built}
    assert not student_rows.leaks_heldout(built, read(args.spec_panel))
    if args.out.exists():
        raise ValueError('preserve previous snapshots; use a fresh output directory')
    args.out.mkdir(parents=True)
    (args.out / 'training-rows.jsonl').write_text(''.join(line + '\n' for line in output))
    (args.out / 'quarantined.jsonl').write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in quarantined))
    (args.out / 'lineage.json').write_text(json.dumps(lineage, indent=2) + '\n')
    report = {'parent_dataset_sha256': DATASET, 'rows': len(output), 'changed_rows': changed,
        'identity_policy': 'Explicit task_id, otherwise the existing loop_filter.problem_id parser applied to name/task.',
        'changed_row_count': len(changed), 'quarantined_row_count': len(quarantined),
        'quarantined_contracts': len({tuple(r['contract_program_sha256s']) for r in quarantined}),
        'quarantined_contract_programs': len({key for r in quarantined for key in r['contract_program_sha256s']}),
        'deduplicated_parent_rows': duplicate_rows, 'prompt_answer_duplicates': 0,
        'kinds': dict(Counter(r.get('kind') or r.get('source') or 'unspecified' for r in built)),
        'judge_python_rows_unchanged': sum(r.get('kind') == 'judge-python' for r in built),
        'development_or_heldout_id_overlap': [], 'specification_panel_text_overlap': [],
        'inputs': {str(path.resolve().relative_to(ENGINE.parent)): digest(path) for path in
            (args.original_audit / 'summary.json', args.repairs / 'summary.json', args.dev,
             args.heldout, args.spec_panel, Path(__file__))},
        'files': {name: digest(args.out / name) for name in
                  ('training-rows.jsonl', 'quarantined.jsonl', 'lineage.json')},
        'scope': 'Corrected positive t contracts and quarantine of measured nonpassing contracts. Original Python targets unchanged. Full held-out lineage audit and token accounting remain required before training.'}
    (args.out / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    assert digest(args.rows) == DATASET
    print(json.dumps({k:report[k] for k in ('rows', 'changed_row_count', 'quarantined_row_count',
                     'quarantined_contract_programs', 'judge_python_rows_unchanged', 'files')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('rows', 'original-audit', 'repairs', 'native-root', 'dev', 'heldout', 'spec-panel', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    build(parser.parse_args())


if __name__ == '__main__':
    main()
