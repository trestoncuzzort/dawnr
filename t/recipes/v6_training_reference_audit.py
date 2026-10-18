"""Check the flagged English training contracts with the existing reference gates.

Run the measurement inside the network-disabled proof container. The wrapper
does not alter any engine module or training row.
Sources: t/spec_check.py and t/recipes/v6_compare.py.
https://github.com/trestoncuzzort/dawnr/blob/main/t/spec_check.py
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import signal
import subprocess
import sys

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))
import spec_check
import spec_experiment as se
from v6_compare import confirmed_specification

DATASET = 'e14f766f06299d589d9a6e3293f6bf3e3f06ffac026433e2fdeff1c04294af80'
AUDIT = '85cce13470d2b4eb326e38759a7ee59ce3ed5d35b1cd95521f9ae8450b6f8296'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(args):
    assert digest(args.rows) == DATASET
    assert digest(args.audit / 'results.jsonl') == AUDIT
    rows = [json.loads(line) for line in args.rows.read_text().splitlines()]
    protocol = json.loads((args.audit / 'protocol.json').read_text())
    results = [json.loads(line) for line in (args.audit / 'results.jsonl').read_text().splitlines()]
    selected = []
    for result in results:
        if result['status'] != 'ok' or not result['survivors']:
            continue
        ids = {rows[index]['task_id'] for index in result['source_rows'] if rows[index].get('task_id') is not None}
        if not ids:
            continue
        assert len(ids) == 1
        key = result['program_sha256']
        source = args.audit / 'tasks' / (key + '.json')
        assert digest(source) == protocol['selected'][key]['task_sha256']
        selected.append({'program_sha256': key, 'task_id': ids.pop(), 'source_rows': result['source_rows'],
                         'task_sha256': digest(source), 'task': json.loads(source.read_text())})
    selected.sort(key=lambda item: item['program_sha256'])
    assert len(selected) == 44 and len({item['task_id'] for item in selected}) == 39
    for panel in (args.dev, args.heldout):
        assert not {item['task_id'] for item in selected} & set(map(int, panel.read_text().split()))
    if args.directory.exists():
        raise ValueError('preserve previous audits; use a fresh directory')
    (args.directory / 'tasks').mkdir(parents=True)
    for item in selected:
        task = item.pop('task')
        path = args.directory / 'tasks' / (item['program_sha256'] + '.json')
        path.write_text(json.dumps(task, sort_keys=True) + '\n')
        assert digest(path) == item['task_sha256']
    manifest = {'dataset_sha256': DATASET, 'strength_results_sha256': AUDIT, 'selected': selected,
        'development_panel_sha256': digest(args.dev), 'heldout_panel_sha256': digest(args.heldout),
        'overlap_with_development_or_heldout_ids': [], 'draws': 1000, 'seed': 1,
        'seconds_per_task': 120, 'memory_mib_per_worker': 8192, 'workers': 4,
        'scope': 'Training-contract diagnostic only. Unknowns are not passes; no automatic training admission.'}
    (args.directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'selected': len(selected), 'task_ids': 39, 'panel_id_overlap': 0}))


def prepare_repairs(args):
    """Bind nine reviewed repairs to their exact original rows and native controls."""
    import check_wf
    import student_rows
    import surface
    from v6_compare import integrity_findings

    assert digest(args.rows) == DATASET
    rows = [json.loads(line) for line in args.rows.read_text().splitlines()]
    selected, evidence = [], {}
    for directory, arm in ((args.initial, 'initial'), (args.direct, 'direct'),
                           (args.length_order, 'length-order')):
        protocol = json.loads((directory / 'protocol.json').read_text())
        assert protocol['dataset_sha256'] == DATASET
        columns, cells = se.parse_kernel_table(directory / 'kernels.md')
        assert set(columns) == set(spec_check.KERNELS)
        assert integrity_findings(cells) == {'contradictions': [], 'unsound_cells': []}
        evidence[arm] = {name: digest(directory / name) for name in
                         ('protocol.json', 'interpreter.json', 'kernels.md')}
        if arm == 'length-order':
            controls = [{'source_row': 187, 'task_id': 202503, 'name': 'findLUSlength',
                'chosen_sha256': protocol['chosen_sha256'],
                'files': {'strengthened': {'name': 'findLUSlength_length_order',
                                          'sha256': protocol['task_sha256']}}}]
            assert json.loads((directory / 'interpreter.json').read_text())['R3_interpreter_holds']
        else:
            controls = protocol['controls']
            if arm == 'initial':
                controls = [item for item in controls if item['name'] == 'move_first']
            interpreter = {item['name']: item for item in json.loads((directory / 'interpreter.json').read_text())}
            assert all(interpreter[item['name']].get('interpreter_holds',
                       interpreter[item['name']].get('R1_holds')) for item in controls)
        for control in controls:
            index, task_id = control['source_row'], control['task_id']
            row = rows[index]
            assert row['task_id'] == task_id
            assert hashlib.sha256(row['chosen'].encode()).hexdigest() == control['chosen_sha256']
            original = surface.parse(se.find_block(row['chosen']))
            info = control['files']['strengthened']
            source = directory / 'tasks' / (info['name'] + '.json')
            assert digest(source) == info['sha256']
            task = json.loads(source.read_text())
            task['name'] = original['name']
            assert not check_wf.check_wf(task)
            assert {k:v for k,v in task.items() if k != 'ensures'} == {
                k:v for k,v in original.items() if k != 'ensures'}
            assert task['ensures'][:len(original['ensures'])] == original['ensures']
            passing = sum(value == 'verified / refuted' for value in cells[info['name']].values())
            if arm == 'length-order':
                assert evidence['initial']['kernels.md'] == protocol['original_kernel_table_sha256']
                _, initial_cells = se.parse_kernel_table(args.initial / 'kernels.md')
                original_passing = sum(value == 'verified / refuted' for value in
                                       initial_cells['findLUSlength_original'].values())
            else:
                original_info = control['files']['original']
                original_path = directory / 'tasks' / (original_info['name'] + '.json')
                assert digest(original_path) == original_info['sha256']
                native_original = json.loads(original_path.read_text())
                native_original['name'] = original['name']
                assert native_original == original
                original_passing = sum(value == 'verified / refuted' for value in
                                       cells[original_info['name']].values())
            assert passing >= original_passing >= 1
            program = student_rows._normalised(task, body=True)
            key = hashlib.sha256(program.encode()).hexdigest()
            original_key = hashlib.sha256(student_rows._normalised(original, body=True).encode()).hexdigest()
            encoded = json.dumps(task, sort_keys=True) + '\n'
            selected.append({'program_sha256': key, 'original_program_sha256': original_key,
                'task_id': task_id, 'source_rows': [index], 'name': task['name'],
                'native_passing_kernels': passing, 'original_native_passing_kernels': original_passing,
                'task_sha256': hashlib.sha256(encoded.encode()).hexdigest(), 'encoded': encoded})
    assert len(selected) == len({v['task_id'] for v in selected}) == 9
    for panel in (args.dev, args.heldout):
        assert not {v['task_id'] for v in selected} & set(map(int, panel.read_text().split()))
    if args.directory.exists():
        raise ValueError('preserve previous audits; use a fresh directory')
    (args.directory / 'tasks').mkdir(parents=True)
    for item in selected:
        (args.directory / 'tasks' / (item['program_sha256'] + '.json')).write_text(item.pop('encoded'))
    manifest = {'kind': 'repaired', 'dataset_sha256': DATASET, 'selected': selected,
        'native_controls': evidence, 'development_panel_sha256': digest(args.dev),
        'heldout_panel_sha256': digest(args.heldout), 'overlap_with_development_or_heldout_ids': [],
        'draws': 1000, 'seed': 1, 'seconds_per_task': 120, 'memory_mib_per_worker': 8192,
        'workers': 4, 'scope': 'Reference validation of nine native-tested repairs. Training rows unchanged.'}
    (args.directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'selected': len(selected), 'panel_id_overlap': 0}))


def worker(directory, key):
    resource.setrlimit(resource.RLIMIT_AS, (8192 * 1024**2, 8192 * 1024**2))
    job = json.loads((directory / 'jobs' / (key + '.json')).read_text())
    task, entry = job['task'], job['entry']
    if entry is None:
        result = {'status': 'problem not in pool', 'confirmed_reference': False}
    else:
        seed = '1:' + spec_check.task_sha256(task)
        verdict = spec_check.check_task(task, entry, 1000, random.Random(seed))
        if verdict.get('status') == 'agrees':
            try:
                verdict['larger'] = spec_check.larger_inputs(task, entry, seed)
            except Exception as error:
                verdict['larger'] = {'status': 'not measured (' + type(error).__name__ + ')'}
        verdict.update(spec_check.check_points(task, entry))
        body_examples = [se.run_point(task, point) for point in entry.get('points', [])]
        confirmed = (verdict.get('status') == 'agrees' and verdict.get('points_held', 0) > 0
            and not verdict.get('points_failed', 0) and not verdict.get('points_excluded', 0)
            and confirmed_specification(verdict)
            and not spec_check.larger_reason(verdict.get('larger'), .6, verdict))
        result = {'status': verdict['status'], 'verdict': verdict, 'body_examples': body_examples,
                  'body_examples_all_pass': bool(body_examples) and all(r['verdict'] == 'pass' for r in body_examples),
                  'confirmed_reference': confirmed}
    (directory / 'results' / (key + '.json')).write_text(json.dumps(result, indent=2) + '\n')


def run(args):
    directory = args.directory
    manifest = json.loads((directory / 'manifest.json').read_text())
    assert (manifest['draws'], manifest['workers'], manifest['seconds_per_task']) == (1000, 4, 120)
    kind = manifest.get('kind', 'flagged-originals')
    count = {'flagged-originals': 44, 'repaired': 9}[kind]
    assert manifest['dataset_sha256'] == DATASET and len(manifest['selected']) == count
    if (directory / 'results').exists():
        raise ValueError('existing run must be observed and preserved, not restarted')
    (directory / 'results').mkdir()
    (directory / 'jobs').mkdir()
    (directory / 'logs').mkdir()
    pool, substituted = spec_check.with_reference_plus(se.pool('v5'), args.reference_plus)
    missing = {item['task_id'] for item in manifest['selected']} - set(pool)
    if missing:
        raise ValueError('restore the source reference inputs before measuring: ' + str(sorted(missing)))
    sources = sorted(ENGINE.glob('*.py')) + [Path(__file__), ENGINE / 'recipes/v6_compare.py']
    runtime = {'reference_plus_sha256': digest(args.reference_plus), 'mbppplus_substitutions': substituted,
               'sources': {str(p.relative_to(ENGINE.parent)): digest(p) for p in sources}}
    (directory / 'runtime.json').write_text(json.dumps(runtime, indent=2) + '\n')
    reused = {}
    if args.reuse:
        previous_summary = json.loads((args.reuse / 'summary.json').read_text())
        previous_runtime = json.loads((args.reuse / 'runtime.json').read_text())
        assert digest(args.reuse / 'manifest.json') == previous_summary['manifest_sha256'] == digest(directory / 'manifest.json')
        assert digest(args.reuse / 'runtime.json') == previous_summary['runtime_sha256']
        assert digest(args.reuse / 'results.jsonl') == previous_summary['results_sha256']
        assert previous_runtime['reference_plus_sha256'] == runtime['reference_plus_sha256']
        scorer_sources = lambda value: {k:v for k,v in value['sources'].items()
                                       if k != 't/recipes/v6_training_reference_audit.py'}
        assert scorer_sources(previous_runtime) == scorer_sources(runtime)
        # The orchestration can gain reuse support; the measured worker must be identical.
        def worker_ast(path):
            node = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'worker')
            return ast.dump(node, include_attributes=False)
        assert worker_ast(args.reuse / 'recipes/v6_training_reference_audit.py') == worker_ast(Path(__file__))
        previous = [json.loads(line) for line in (args.reuse / 'results.jsonl').read_text().splitlines()]
        assert len(previous) == previous_summary['programs'] == len(manifest['selected'])
        assert {v['program_sha256'] for v in previous} == {v['program_sha256'] for v in manifest['selected']}
        reused = {v['program_sha256']: v for v in previous}
    for item in manifest['selected']:
        key = item['program_sha256']
        path = directory / 'tasks' / (key + '.json')
        assert digest(path) == item['task_sha256']
        job = {'task': json.loads(path.read_text()), 'entry': pool.get(item['task_id'])}
        job_path = directory / 'jobs' / (key + '.json')
        job_path.write_text(json.dumps(job) + '\n')
        if key in reused:
            previous_job = json.loads((args.reuse / 'jobs' / (key + '.json')).read_text())
            if previous_job != json.loads(job_path.read_text()):
                del reused[key]
            else:
                assert all(reused[key][k] == item[k] for k in ('task_id', 'source_rows', 'task_sha256'))
                (directory / 'results' / (key + '.json')).write_text(json.dumps(reused[key], indent=2) + '\n')

    def measure(item):
        key = item['program_sha256']
        result_path = directory / 'results' / (key + '.json')
        with (directory / 'logs' / (key + '.log')).open('w') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker',
                '--directory', str(directory), '--key', key], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                result = {'status': 'timeout', 'confirmed_reference': False}
            else:
                result = (json.loads(result_path.read_text()) if code == 0 and result_path.exists()
                          else {'status': 'worker failure', 'exit_code': code, 'confirmed_reference': False})
        result.update({k: item[k] for k in ('program_sha256', 'task_id', 'source_rows', 'task_sha256')})
        result_path.write_text(json.dumps(result, indent=2) + '\n')
        return result

    results = list(reused.values())
    with (directory / 'results.jsonl').open('w') as stream, ThreadPoolExecutor(max_workers=4) as executor:
        for result in results:
            stream.write(json.dumps(result, sort_keys=True) + '\n')
        stream.flush()
        print(f'Reused {len(reused)} unchanged reference checks; measuring {count-len(reused)}.', flush=True)
        pending = {executor.submit(measure, item) for item in manifest['selected'] if item['program_sha256'] not in reused}
        for future in as_completed(pending):
            result = future.result()
            results.append(result)
            stream.write(json.dumps(result, sort_keys=True) + '\n')
            stream.flush()
            print(f"{len(results)}/{count} {result['task_id']} {result['status']} confirmed={result['confirmed_reference']}", flush=True)
    assert len(results) == count
    confirmed = sum(r['confirmed_reference'] for r in results)
    summary = {'programs': len(results), 'task_ids': len({r['task_id'] for r in results}),
        'statuses': dict(Counter(r['status'] for r in results)), 'confirmed_reference': confirmed,
        'not_confirmed': len(results) - confirmed,
        'reused_programs': len(reused), 'newly_measured_programs': len(results) - len(reused),
        'body_examples_all_pass': sum(r.get('body_examples_all_pass', False) for r in results),
        'manifest_sha256': digest(directory / 'manifest.json'), 'runtime_sha256': digest(directory / 'runtime.json'),
        'results_sha256': digest(directory / 'results.jsonl')}
    if kind == 'flagged-originals':
        summary['R4_holds'] = len(results) - confirmed >= 10
    else:
        summary['R6_holds'] = confirmed == count and summary['body_examples_all_pass'] == count
    (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (directory / 'COMPLETE').touch()
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'prepare-repairs', 'run', 'worker'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--rows', type=Path)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--dev', type=Path)
    parser.add_argument('--heldout', type=Path)
    parser.add_argument('--reference-plus', type=Path)
    parser.add_argument('--reuse', type=Path)
    parser.add_argument('--key')
    parser.add_argument('--initial', type=Path)
    parser.add_argument('--direct', type=Path)
    parser.add_argument('--length-order', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare(args)
    elif args.mode == 'prepare-repairs':
        prepare_repairs(args)
    elif args.mode == 'run':
        run(args)
    else:
        worker(args.directory, args.key)


if __name__ == '__main__':
    main()
