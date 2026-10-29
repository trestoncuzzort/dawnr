"""Artifact scores must match complete original inputs, without new grading."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent / 'recipes'))
import complete_empty_grade as empty
import release_grade_audit as audit


def encoded(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def write(path, value):
    path.write_bytes(encoded(value))


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('content auditing must not execute a model, program, reference or prover')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(audit.spec_ceiling, 'judge', forbidden)
    monkeypatch.setattr(audit.pair.spec_check, 'check_task', forbidden)
    monkeypatch.setattr(audit.pair.se, 'run_point', forbidden)


@pytest.fixture
def development(tmp_path, monkeypatch):
    tag = 'empty-control'; root = tmp_path / 'artifact'
    directory = root / 'spec-experiment' / tag
    (directory / 'raw').mkdir(parents=True); (directory / 'tasks').mkdir()
    panel = tmp_path / 'panel.txt'; panel.write_text('1\n2\n')
    summary = {'problems': 2, 'answered': 0, 'per_problem': {'1': {'taken': None}, '2': {'taken': None}}}
    write(directory / 'spec_first.json', summary)
    write(directory / 'extract.json', {}); write(directory / 'tests.json', {})
    graded = root / 'v5-repair-20261021/proof-results' / tag; graded.mkdir(parents=True)
    sources = {'t/recipes/complete_empty_grade.py': audit.digest(Path(empty.__file__)),
               't/out/panel.txt': audit.digest(panel)}
    sources.update({'t/' + Path(module.__file__).name: audit.digest(Path(module.__file__))
                    for module in (audit.pair.se, audit.pair.score_levels, audit.pair.spec_check)})
    write(graded / 'evaluator.json', sources)
    monkeypatch.setattr(empty.se, 'OUT_ROOT', root / 'spec-experiment')
    assert empty.complete(tag, panel, graded)
    original = {'spec_first.json': (directory / 'spec_first.json').read_bytes()}
    return (root, tag, panel.read_bytes(), original, sources), directory, graded


def test_complete_zero_part_is_retained(development):
    args, _, _ = development
    result = audit.development(*args)
    assert result['sets']['1'] == result['sets']['7'] == []
    assert result['panel_problems'] == 2


@pytest.mark.parametrize('change', ['input', 'raw', 'extract', 'task', 'tests', 'source', 'panel', 'zero-receipt', 'levels', 'sentinel'])
def test_mismatched_development_evidence_is_refused(development, change):
    args, directory, graded = development
    if change == 'input': write(directory / 'spec_first.json', {})
    elif change == 'raw': write(directory / 'raw/1.json', {})
    elif change == 'extract': write(directory / 'extract.json', {'1': {'stage': 'parse'}})
    elif change == 'task': write(directory / 'tasks/foreign.json', {'name': 'foreign'})
    elif change == 'tests': write(directory / 'tests.json', {'1': {'name': 'foreign'}})
    elif change == 'source': write(graded / 'evaluator.json', {})
    elif change == 'panel': args = (args[0], args[1], b'2\n3\n', *args[3:])
    elif change == 'zero-receipt':
        receipt = audit.read(graded / 'empty-grade.json'); receipt['kernel_or_reference_calls'] = 1
        write(graded / 'empty-grade.json', receipt)
    elif change == 'levels': write(graded / 'levels.json', {})
    else: (graded / 'GRADED').unlink()
    with pytest.raises((ValueError, SystemExit)):
        audit.development(*args)


def test_table_rejects_duplicates_but_accepts_existing_summary_sections(tmp_path):
    path = tmp_path / 'table.md'
    header = '| task | ' + ' | '.join(audit.pair.spec_check.KERNELS) + ' |\n'
    row = '| q | ' + ' | '.join(['verified / refuted'] * 7) + ' |\n'
    path.write_text(header + row + '\n## Summary\n\n| kernel | count |\n| dafny | 1 |\n')
    assert set(audit.table(path, {'q'})) == {'q'}
    path.write_text(header + row + row)
    with pytest.raises(ValueError, match='duplicate'):
        audit.table(path, {'q'})
    path.write_text(header + row.replace('verified / refuted', 'refuted / refuted', 1))
    with pytest.raises(ValueError, match='contradictory'):
        audit.table(path, {'q'})


@pytest.fixture
def precision(tmp_path, monkeypatch):
    panel = b'1\n2\n'; panel_sha = hashlib.sha256(panel).hexdigest()
    monkeypatch.setattr(audit.inputs, 'PANELS', [{'sha256': panel_sha}])
    original = {'panel.txt': panel,
                'spec_first.json': encoded({'problems': 2, 'per_problem': {'1': {'python': 0}, '2': {'python': None}}}),
                'python.jsonl': (json.dumps({'task_id': 1}) + '\n').encode()}
    scored = [{'task_id': 1, 'source': f'spec/{i}', 'verdict': verdict,
               'scores': {'completeness': 1, 'correctness': 1}, 'spec': 'fixture'}
              for i, verdict in enumerate(['kept', 'duplicate', 'kept', 'dropped', 'unscorable'])]
    original['scored-specs.jsonl'] = ''.join(json.dumps(row) + '\n' for row in scored).encode()
    manifest = {'tag': 'fixture-spec20', 'files': {k: hashlib.sha256(v).hexdigest() for k, v in original.items()}}
    original['manifest.json'] = encoded(manifest)
    result = {'tag': manifest['tag'], 'draws': 200, 'problems': 2, 'with_python': 1,
              'python_pass_at_k': {str(k): 1 for k in range(1, 11)}, 'candidates_scored': 5,
              'spec_pass_at_k': {label: {str(k): 1 for k in range(1, 6)} for label in ('safe_gate', 'reference')},
              'safe_kept': 2, 'safe_kept_reference_correct': 1, 'safe_precision': .5,
              'problems_with_a_reference_correct_candidate': 1, 'selection_gap': [],
              'per_problem': {'1': {'candidates': 5, 'safe_kept': 2, 'reference_correct': ['spec/0', 'spec/1', 'spec/3'],
                                    'top_kept_reference_correct': ['spec/0'], 'first_reference_sample': 0, 'first_safe_sample': 0}},
              'reference_statuses': {'agrees': 3, 'disagrees': 1, 'unparsable': 1}}
    sources = {'t/recipes/spec_ceiling.py': audit.digest(Path(audit.spec_ceiling.__file__))}
    write(tmp_path / 'result.json', result)
    receipt = {'grader_commit': '01c94ef5509fc51ab6484c1350c1cb9f8504e459',
               'procedure': {'pool': 'v5', 'draws': 200, 'per_problem': 3, 'jobs': 4},
               'source_sha256': sources, 'input_manifest': manifest, 'input_asset_sha256': 'b' * 64,
               'workflow_run': '7', 'result_sha256': audit.digest(tmp_path / 'result.json')}
    write(tmp_path / 'receipt.json', receipt)
    (tmp_path / 'COMPLETE').write_text(audit.digest(tmp_path / 'receipt.json') + '\n')
    return tmp_path, original, sources, 'b' * 64, 7


def test_precision_recomputes_all_derived_counts_without_reference_execution(precision):
    result = audit.precision(*precision)
    assert result['safe_kept'] == 2 and result['reference_correct'] == 1 and result['precision'] == .5


@pytest.mark.parametrize('change', ['count', 'ratio', 'curve', 'coverage', 'foreign-reference', 'duplicate-reference', 'status-count'])
def test_precision_detects_bad_aggregates_even_with_updated_file_hashes(precision, change):
    root = precision[0]; result = audit.read(root / 'result.json')
    if change == 'count': result['safe_kept_reference_correct'] = 2
    elif change == 'ratio': result['safe_precision'] = .7
    elif change == 'curve': result['spec_pass_at_k']['reference']['1'] = 0
    elif change == 'coverage': result['per_problem']['2'] = deepcopy(result['per_problem']['1'])
    elif change == 'foreign-reference': result['per_problem']['1']['reference_correct'].append('spec/18')
    elif change == 'duplicate-reference': result['per_problem']['1']['reference_correct'].append('spec/0')
    else: result['reference_statuses']['agrees'] += 1
    write(root / 'result.json', result)
    receipt = audit.read(root / 'receipt.json'); receipt['result_sha256'] = audit.digest(root / 'result.json')
    write(root / 'receipt.json', receipt); (root / 'COMPLETE').write_text(audit.digest(root / 'receipt.json'))
    with pytest.raises(ValueError):
        audit.precision(*precision)


@pytest.fixture
def spec33(tmp_path, monkeypatch):
    import student_rows
    questions = [student_rows.row_for(audit.grade_spec33.scorer.surface.parse(
        f't 0\ntask q{i}(x: int) returns (y: int)\n ensures y == x\n{{ y := x; }}\n')) for i in range(33)]
    qpath = tmp_path / 'questions.jsonl'; apath = tmp_path / 'answers.jsonl'
    qpath.write_text(''.join(json.dumps(row) + '\n' for row in questions))
    apath.write_text(''.join(json.dumps({'name': row['name'], 'reply': row['chosen'] if i == 0 else 'no program',
                                      'model': 'fixture', 'system': 's1'}) + '\n' for i, row in enumerate(questions)))
    monkeypatch.setattr(audit.grade_spec33, 'QUESTIONS_SHA', audit.digest(qpath))
    manifest = {'label': 'fixture', 'answer_model': 'fixture',
                'questions': {'path': qpath.name, 'sha256': audit.digest(qpath)},
                'answers': {'path': apath.name, 'sha256': audit.digest(apath)}}
    mpath = tmp_path / 'manifest.json'; write(mpath, manifest)
    root = tmp_path / 'result'; root.mkdir()
    answers = {r['name']: r['reply'] for r in audit.grade_spec33.read_rows(apath)}
    prepared = audit.grade_spec33.scorer.prepare(questions, answers, root / 'tasks')
    write(root / 'spec-report.json', prepared)
    (root / 'spec-kernels.md').write_text('| task | ' + ' | '.join(audit.pair.spec_check.KERNELS)
        + ' |\n| q0 | ' + ' | '.join(['verified / refuted'] * 7) + ' |\n')
    levels = audit.grade_spec33.checked_levels(prepared, root / 'spec-kernels.md')
    write(root / 'spec-levels.json', levels)
    sources = {'t/score_spec_given.py': audit.digest(Path(audit.grade_spec33.scorer.__file__))}
    receipt = {**manifest, 'input_manifest_sha256': audit.digest(mpath), 'levels': levels,
               'passes_spec33_requirement': False, 'code_sha256': sources}
    write(root / 'receipt.json', receipt); (root / 'GRADED').write_text(audit.digest(root / 'receipt.json'))
    return root, mpath, sources


def test_spec33_reconstructs_original_tasks_and_scores_without_provers(spec33):
    result = audit.spec33(*spec33)
    assert result['levels']['proved by all seven'] == 1 and result['preparation_recomputed']


@pytest.mark.parametrize('change', ['task', 'report', 'levels', 'table'])
def test_spec33_altered_evidence_is_refused(spec33, change):
    root = spec33[0]
    if change == 'task': write(root / 'tasks/q0.json', {})
    elif change == 'report': write(root / 'spec-report.json', {})
    elif change == 'levels': write(root / 'spec-levels.json', {})
    else: (root / 'spec-kernels.md').unlink()
    with pytest.raises(ValueError):
        audit.spec33(*spec33)
