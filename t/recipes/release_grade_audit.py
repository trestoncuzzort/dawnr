"""Audit authenticated cloud-grade contents against original generation inputs.

The caller verifies workflow identity and archive digests before using these
readers. This module checks contents and recomputes scores, without model calls,
program execution, reference evaluation or proof invocation.
Sources: v7_local_pair.py, v6_compare.py, grade_spec33.py, spec_ceiling.py;
https://github.com/trestoncuzzort/dawnr/blob/main/t/recipes/spec_ceiling.py
"""
from collections import defaultdict
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile

import grade_spec33
import release_grading_inputs as inputs
import release_seed_selection as selection
import spec_ceiling
import v7_local_pair as pair

require = inputs.require
digest = inputs.digest
canonical = selection.canonical


def read(path):
    return json.loads(Path(path).read_text())


def files(directory):
    directory = Path(directory)
    require(not directory.is_symlink(), 'linked evidence directory')
    result = {}
    for path in directory.rglob('*') if directory.exists() else []:
        require(not path.is_symlink() and (path.is_file() or path.is_dir()), 'linked or special evidence file')
        if path.is_file():
            result[str(path.relative_to(directory))] = digest(path)
    return result


def sources(actual, expected):
    require(expected and actual == expected, 'evaluator source identity differs')
    for name, value in expected.items():
        inputs.safe_name(name)
        selection.check_digest(value)


def reader_sources(expected, modules):
    root = Path(__file__).resolve().parents[2]
    for module in modules:
        path = Path(module.__file__).resolve()
        name = str(path.relative_to(root))
        require(name in expected and digest(path) == expected[name], 'local reader differs from the frozen procedure')


def table(path, expected):
    """The existing table parser plus an explicit duplicate-row/header check."""
    path = Path(path)
    if not path.exists():
        require(not expected, 'missing kernel table')
        return {}
    columns, cells = pair.se.parse_kernel_table(path)
    names, headers, active = [], 0, False
    for line in path.read_text().splitlines():
        if not line.startswith('|'):
            active = False
            continue
        values = [value.strip() for value in line.strip().strip('|').split('|')]
        if values[0] == 'task':
            headers += 1
            active = True
        elif active and set(values[0]) - {'-', ':', ' '}:
            require(len(values) == 8, 'incomplete kernel row')
            names.append(values[0])
    require(headers == 1 and len(columns) == len(set(columns)) == 7
            and set(columns) == set(pair.spec_check.KERNELS), 'incomplete kernel columns')
    require(len(names) == len(set(names)) and set(names) == set(cells) == set(expected),
            'missing, duplicate or foreign kernel row')
    require(not any(pair.integrity_findings(cells).values()), 'contradictory or unsound kernel outcomes')
    return cells


def original_files(directory, originals):
    for name, data in originals.items():
        inputs.safe_name(name)
        path = Path(directory) / name
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == data,
                'graded input differs from the original generation')


def development(root, tag, panel_bytes, originals, expected_sources):
    root = Path(root)
    inputs.safe_name(tag)
    require('/' not in tag, 'invalid generation tag')
    directory = root / 'spec-experiment' / tag
    graded = root / 'v5-repair-20261021/proof-results' / tag
    hashes = files(root)
    ids = panel_bytes.decode().split()
    require(ids and len(ids) == len(set(ids)) and all(str(int(i)) == i for i in ids), 'invalid problem panel')
    require('spec_first.json' in originals, 'original generation summary is missing')
    required_originals = {name: data for name, data in originals.items()
                          if name == 'spec_first.json' or name.startswith('raw/')}
    original_files(directory, required_originals)
    summary, taken = inputs.check_summary((directory / 'spec_first.json').read_bytes(), set(ids))
    require(type(summary['answered']) is int, 'invalid answer count')
    raw = files(directory / 'raw')
    require(set(raw) == {tid + '.json' for tid in taken}
            and {name for name in required_originals if name.startswith('raw/')} == {'raw/' + name for name in raw},
            'raw answer accounting differs')
    extracted, tests = read(directory / 'extract.json'), read(directory / 'tests.json')
    require(set(extracted) == taken, 'extraction omitted or added an answer')
    ready = {tid: entry['name'] for tid, entry in extracted.items() if entry.get('stage') == 'task'}
    require(len(set(ready.values())) == len(ready) and set(tests) == set(ready), 'task/test accounting differs')
    tasks = files(directory / 'tasks')
    require(set(tasks) == {name + '.json' for name in ready.values()}, 'missing or foreign task file')
    for tid, name in ready.items():
        require(read(directory / 'tasks' / (name + '.json'))['name'] == name
                and tests[tid]['name'] == name, 'task identity differs')
    sources(read(graded / 'evaluator.json'), expected_sources)
    # Reconstruct extracted tasks with the same parser/static checks. Test-point
    # verdicts and prover outcomes remain those of the frozen cloud grader.
    reader_sources(expected_sources, (pair.se, pair.score_levels, pair.spec_check))
    with tempfile.TemporaryDirectory() as temporary:
        copy = Path(temporary)
        (copy / 'raw').mkdir(); (copy / 'tasks').mkdir()
        for name, data in required_originals.items():
            (copy / name).write_bytes(data)
        with redirect_stdout(io.StringIO()):
            status = pair.se.extract_tag(copy, promote_header=True)
        require(status == 0 and read(copy / 'extract.json') == extracted
                and files(copy / 'tasks') == tasks, 'extraction differs from the original saved answers')
    panel_keys = [name for name in expected_sources if name.startswith('t/out/')]
    require(len(panel_keys) == 1 and expected_sources[panel_keys[0]] == hashlib.sha256(panel_bytes).hexdigest(),
            'grader panel identity differs')
    table(directory / 'kernels.md', set(ready.values()))
    old_root = pair.se.OUT_ROOT
    try:
        pair.se.OUT_ROOT = root / 'spec-experiment'
        record, sets, _ = pair.arm(tag + ':' + str(graded), set(map(int, ids)))
    finally:
        pair.se.OUT_ROOT = old_root
    empty = graded / 'empty-grade.json'
    if not ready and 't/recipes/complete_empty_grade.py' in expected_sources:
        receipt = read(empty)
        require(receipt['kind'] == 'complete-zero-task-grade' and receipt['tag'] == tag
                and receipt['panel_problems'] == len(ids) and receipt['panel_sha256'] == hashlib.sha256(panel_bytes).hexdigest()
                and receipt['saved_raw_answers'] == len(raw) and receipt['kernel_or_reference_calls'] == 0
                and receipt['procedure_sha256'] == expected_sources['t/recipes/complete_empty_grade.py']
                and receipt['evaluator_sha256'] == digest(graded / 'evaluator.json')
                and receipt['raw_sha256'] == raw
                and receipt['input_sha256'] == {name: digest(directory / name)
                                              for name in ('spec_first.json', 'extract.json', 'tests.json')},
                'zero-task receipt differs')
    else:
        require(not empty.exists(), 'nonempty grade has a zero-task receipt')
    return {'kind': 'audited-development-part', 'tag': tag, 'panel_problems': len(ids),
            'panel_sha256': hashlib.sha256(panel_bytes).hexdigest(), 'reading': record,
            'sets': {key: sorted(value) for key, value in sets.items()}, 'files_sha256': hashes,
            'evaluator_sha256': digest(graded / 'evaluator.json'), 'source_entries': len(expected_sources)}


def precision(root, original, expected_sources, asset_sha, run_id):
    """Recompute derived counts from the frozen instrument's reference source lists.

The original reference classifications are retained, not independently rerun.
"""
    root = Path(root)
    require(set(original) == {'manifest.json', 'panel.txt', 'spec_first.json', 'python.jsonl', 'scored-specs.jsonl'},
            'precision inputs are incomplete')
    receipt, result = read(root / 'receipt.json'), read(root / 'result.json')
    require((root / 'COMPLETE').read_text().strip() == digest(root / 'receipt.json')
            and receipt['result_sha256'] == digest(root / 'result.json'), 'precision completion digest differs')
    sources(receipt['source_sha256'], expected_sources)
    reader_sources(expected_sources, (spec_ceiling,))
    manifest = json.loads(original['manifest.json'])
    require(manifest['files'] == {name: hashlib.sha256(data).hexdigest() for name, data in original.items() if name != 'manifest.json'}
            and receipt['input_manifest'] == manifest and receipt['input_asset_sha256'] == asset_sha
            and str(receipt['workflow_run']) == str(run_id), 'precision input/run identity differs')
    require(receipt['grader_commit'] == '01c94ef5509fc51ab6484c1350c1cb9f8504e459'
            and receipt['procedure'] == {'pool': 'v5', 'draws': 200, 'per_problem': 3, 'jobs': 4}, 'precision procedure differs')
    require(hashlib.sha256(original['panel.txt']).hexdigest() == inputs.PANELS[0]['sha256'], 'precision panel differs')
    ids = original['panel.txt'].decode().split()
    summary, _ = inputs.check_summary(original['spec_first.json'], set(ids), answers_required=False)
    attempts = {tid: summary['per_problem'][tid].get('python') for tid in ids}
    require(all(value is None or selection.integer(value, 0, 9) for value in attempts.values()), 'invalid Python attempt')
    passing = [tid for tid in ids if attempts[tid] is not None]
    pyids = [str(row['task_id']) for row in inputs.read_jsonl(original['python.jsonl'])]
    require(len(pyids) == len(set(pyids)) and set(pyids) == set(passing), 'precision Python accounting differs')
    scored = inputs.read_jsonl(original['scored-specs.jsonl'])
    by, keys = defaultdict(list), set()
    for row in scored:
        tid, source = str(row['task_id']), row['source']
        require(tid in passing and (tid, source) not in keys
                and 0 <= spec_ceiling._sample_index(source) < 20, 'foreign or duplicate precision candidate')
        require(row['verdict'] in ('kept', 'dropped', 'duplicate', 'unscorable'), 'unknown scored verdict')
        keys.add((tid, source)); by[tid].append(row)
    require(all(len(rows) <= 20 for rows in by.values()) and set(result['per_problem']) == set(passing),
            'precision per-problem coverage differs')
    details, gap, first_ref, first_safe = {}, [], {}, {}
    kept_count = correct_count = 0
    for tid in passing:
        rows = by[tid]
        refs = result['per_problem'][tid]['reference_correct']
        require(isinstance(refs, list) and len(refs) == len(set(refs))
                and set(refs) <= {r['source'] for r in rows}, 'foreign reference classification')
        ordered = sorted(rows, key=lambda r: spec_ceiling._sample_index(r['source']))
        first_ref[tid] = next((spec_ceiling._sample_index(r['source']) for r in ordered if r['source'] in refs), None)
        first_safe[tid] = next((spec_ceiling._sample_index(r['source']) for r in ordered if r['verdict'] in ('kept', 'duplicate')), None)
        kept = [r for r in rows if r['verdict'] == 'kept']
        kept_count += len(kept); correct_count += sum(r['source'] in refs for r in kept)
        kept.sort(key=lambda r: (-r['scores']['completeness'], -r['scores']['correctness']))
        top_refs = [r['source'] for r in kept[:3] if r['source'] in refs]
        details[tid] = {'candidates': len(rows), 'safe_kept': len(kept),
                        'reference_correct': [r['source'] for r in rows if r['source'] in refs],
                        'top_kept_reference_correct': top_refs, 'first_reference_sample': first_ref[tid],
                        'first_safe_sample': first_safe[tid]}
        if refs and not top_refs:
            gap.append(tid)
    python_k = max([value for value in attempts.values() if value is not None] + [0]) + 1
    spec_k = max([spec_ceiling._sample_index(r['source']) for r in scored] + [0]) + 1
    statuses = result['reference_statuses']
    require(isinstance(statuses, dict) and all(selection.integer(n) for n in statuses.values())
            and sum(statuses.values()) == len(scored), 'reference status accounting differs')
    rebuilt = {'tag': manifest['tag'], 'draws': 200, 'problems': len(ids), 'with_python': len(passing),
               'python_pass_at_k': {k: sum(v is not None and v < k for v in attempts.values()) for k in range(1, max(python_k, 10) + 1)},
               'candidates_scored': len(scored),
               'spec_pass_at_k': {label: {k: sum(v is not None and v < k for v in values.values()) for k in range(1, spec_k + 1)}
                                  for label, values in (('safe_gate', first_safe), ('reference', first_ref))},
               'safe_kept': kept_count, 'safe_kept_reference_correct': correct_count,
               'safe_precision': correct_count / kept_count if kept_count else None,
               'problems_with_a_reference_correct_candidate': sum(v is not None for v in first_ref.values()),
               'selection_gap': gap, 'per_problem': details, 'reference_statuses': statuses}
    require(canonical(result) == canonical(rebuilt), 'precision aggregate differs from the saved candidates')
    return {'kind': 'audited-precision', 'safe_kept': kept_count, 'reference_correct': correct_count,
            'precision': rebuilt['safe_precision'], 'files_sha256': files(root),
            'reference_classifications': 'authenticated frozen cloud grader; no local reference rerun'}


def spec33(root, input_manifest, expected_sources):
    root = Path(root)
    receipt = read(root / 'receipt.json')
    require((root / 'GRADED').read_text().strip() == digest(root / 'receipt.json'), 'spec33 completion digest differs')
    sources(receipt['code_sha256'], expected_sources)
    reader_sources(expected_sources, (grade_spec33.scorer,))
    manifest, questions, answers = grade_spec33.validate_inputs(Path(input_manifest))
    require(receipt['input_manifest_sha256'] == digest(input_manifest)
            and all(receipt[name] == manifest[name] for name in ('label', 'answer_model', 'questions', 'answers')),
            'spec33 input identity differs')
    with tempfile.TemporaryDirectory() as temporary:
        tasks = Path(temporary) / 'tasks'
        prepared = grade_spec33.scorer.prepare(questions, answers, tasks, normalise_name=False)
        require(prepared == read(root / 'spec-report.json') and files(tasks) == files(root / 'tasks'),
                'spec33 preparation differs from the original answers')
    ready = {name for name, row in prepared['entries'].items() if row['stage'] == 'ready'}
    table(root / 'spec-kernels.md', ready)
    levels = grade_spec33.checked_levels(prepared, root / 'spec-kernels.md')
    require(levels == read(root / 'spec-levels.json') == receipt['levels']
            and receipt['passes_spec33_requirement'] is (levels['proved by all seven'] >= 27),
            'spec33 levels differ from the complete table')
    return {'kind': 'audited-spec33', 'levels': levels, 'files_sha256': files(root),
            'preparation_recomputed': True, 'model_reference_or_prover_calls': 0}
