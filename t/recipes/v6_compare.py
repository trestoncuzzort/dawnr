"""Audit the frozen paired evaluation and apply the registered v6 release floors.

Prior art: v5-matched-2026-10-11-compare.py, score_levels.tag_levels,
score_spec_given.level_of, and spec_check.complete. Missing coverage is an
error; an unknown completeness measurement is never promoted to a pass.
https://github.com/trestoncuzzort/dawnr/blob/main/t/score_levels.py
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import score_levels
import score_spec_given
import spec_check
import spec_experiment as se
from v6_candidate import validate_export, validate_selection


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def confirmed_specification(verdict):
    larger = verdict.get('larger') or {}
    return (spec_check.complete(verdict, .6) is True
            and larger.get('status') == 'agrees'
            and larger.get('draws', 0) >= spec_check.MIN_LARGER
            and spec_check.complete(larger, .6) is True)


def integrity_findings(cells):
    contradictions, unsound = [], []
    for name, row in cells.items():
        if {'verified', 'refuted'} <= {v.split(' / ')[0] for v in row.values()}:
            contradictions.append(name)
        unsound.extend([name, kernel] for kernel, value in row.items() if value.endswith(' / unsound'))
    return {'contradictions': contradictions, 'unsound_cells': unsound}


def kernel_outcomes(cells):
    return {kernel: dict(Counter(row[kernel] for row in cells.values())) for kernel in spec_check.KERNELS}


def problems(root, arm, ids):
    tag = f'v6-20261018-{arm}-heldout'
    generated, graded = root/f'{arm}-heldout', root/f'{arm}-heldout-full'
    assert (generated/'GENERATED').is_file() and (graded/'GRADED').is_file(), arm+' incomplete'
    protocol = read(generated/'requests/protocol.json')
    assert read(generated/'requests/completed.json') == protocol
    assert protocol['panel_sha256'] == digest(root/'clean-182.txt')
    assert protocol['route_args'] == [
        '--tag', tag, '--ids-file', 't/out/v6-20261018/clean-182.txt', '--pool', 'v5',
        '--python', '3', '--spec-samples', '4', '--per-problem', '3', '--samples', '2',
        '--max-new', '1024', '--batch', '16']
    directory = se.OUT_ROOT/tag
    summary = read(directory/'spec_first.json')
    assert summary['problems'] == len(ids) and set(map(int, summary['per_problem'])) == ids
    taken = {int(i) for i, result in summary['per_problem'].items() if result.get('taken') is not None}
    assert {int(p.stem) for p in (directory/'raw').glob('*.json')} == taken
    assert summary['answered'] == len(taken)
    columns, cells = se.parse_kernel_table(directory/'kernels.md')
    tasks = {read(p)['name'] for p in (directory/'tasks').glob('*.json')}
    assert set(columns) == set(spec_check.KERNELS) and set(cells) == tasks
    verdicts = read(graded/'verdicts.json')['results']
    assert set(verdicts) == {tag+'/'+name for name in tasks}
    rows, pooled = score_levels.table([tag], ids, verdicts, .6, True)
    assert read(graded/'levels.json') == {'rows': rows, 'pooled': pooled, 'ids': len(ids)}
    levels = score_levels.tag_levels(tag, ids, verdicts, .6, True)
    extracted = read(directory/'extract.json')
    unconfirmed = []
    for tid, values in levels.items():
        if values[0] and not confirmed_specification(verdicts[tag+'/'+extracted[str(tid)]['name']]):
            unconfirmed.append(tid)
    sets = {str(k): {i for i, values in levels.items() if values[0] >= k and i not in unconfirmed}
            for k in score_levels.LEVELS}
    return {'protocol': protocol, 'sets': sets, 'evaluator': read(graded/'evaluator.json'),
            'registered_counts': rows[0], 'unconfirmed_admissions': sorted(unconfirmed),
            'generation_stages': {k:v for k,v in summary.items() if k != 'per_problem'},
            'kernel_outcomes': kernel_outcomes(cells), 'integrity': integrity_findings(cells)}


def specifications(root, arm):
    generated, graded = root/f'{arm}-heldout/spec', root/f'{arm}-spec-full'
    assert (graded/'GRADED').is_file(), arm+' specification grading incomplete'
    protocol = read(generated/'protocol.json')
    assert protocol['questions_sha256'] == digest(root/'spec-heldout.jsonl')
    assert (protocol['system'], protocol['max_new'], protocol['temperature'], protocol['top_p'],
            protocol['attempts']) == ('s1', 1024, 0, .95, 1)
    assert read(generated/'completed.json') == {
        'protocol_sha256': digest(generated/'protocol.json'),
        'answers_sha256': digest(generated/'answers.jsonl'), 'questions': 33}
    names = [json.loads(s)['name'] for s in (root/'spec-heldout.jsonl').read_text().splitlines() if s.strip()]
    answers = [json.loads(s)['name'] for s in (generated/'answers.jsonl').read_text().splitlines()]
    assert len(names) == len(set(names)) == len(answers) == len(set(answers)) == 33
    assert set(answers) == set(names)
    report = read(graded/'report.json')
    assert report['questions'] == 33 and report['name_normalised'] is False
    assert set(report['entries']) == set(names) and not report['stages'].get('unanswered')
    columns, cells = se.parse_kernel_table(graded/'kernels.md')
    ready = {name for name, entry in report['entries'].items() if entry['stage'] == 'ready'}
    assert set(columns) == set(spec_check.KERNELS) and set(cells) == ready
    levels = {name: score_spec_given.level_of(cells.get(name))[1] if name in ready else 0 for name in names}
    assert read(graded/'levels.json') == score_spec_given.levels(report, graded/'kernels.md')
    return {'protocol': protocol, 'evaluator': read(graded/'evaluator.json'),
            'sets': {str(k): {n for n, level in levels.items() if level >= k} for k in score_levels.LEVELS},
            'stages': report['stages'], 'kernel_outcomes': kernel_outcomes(cells),
            'integrity': integrity_findings(cells)}


def decision(baseline, candidate, integrity_ok=True):
    checks = {
        'clean_182_gain': candidate['one'] >= baseline['one'] + 1,
        'clean_182_floor': candidate['one'] >= 18,
        'all_seven_nonregression': candidate['seven'] >= baseline['seven'],
        'all_seven_floor': candidate['seven'] >= 12,
        'specification_nonregression': candidate['spec'] >= baseline['spec'],
        'specification_floor': candidate['spec'] >= 27,
        'no_contradiction_or_unsound_cell': integrity_ok,
    }
    return {'qualified': all(checks.values()), 'checks': checks}


def paired(a, b):
    return {'v5': len(a), 'v6': len(b), 'difference': len(b)-len(a),
            'gained': sorted(b-a), 'lost': sorted(a-b), 'both': sorted(a&b)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('t/out/v6-20261018'))
    args = parser.parse_args(argv)
    root = args.root
    selected = read(root/'candidate-frozen.json')
    development_path = root/'selection-development.json'
    assert digest(development_path) == selected['development_receipt_sha256']
    candidate = validate_selection(selected, read(development_path))
    exported_root = root/f'export-{candidate}-receipts'
    package_root = exported_root/'release'
    package = read(package_root/'package.json')
    validate_export(selected, read(exported_root/'export.json'), package)
    assert digest(package_root/'dawnr-student.sha256') == selected['candidate_release_manifest_sha256']
    for name in ('clean-182.txt', 'spec-heldout.jsonl'):
        assert selected['panels'][name] == digest(root/name)
    ids = {int(s) for s in (root/'clean-182.txt').read_text().split()}
    assert len(ids) == 182 and ids == score_levels.panel_ids(Path('t/out/loop/split-v5.json'), 'clean-182', None)
    arms = {}
    for arm in ('v5', 'v6'):
        meta = read(root/f'{arm}-heldout/generation.json')
        assert meta['arm'] == arm and meta['candidate_lock_sha256'] == digest(root/'candidate-frozen.json')
        model_sha = ('d855000c3dffd9772da5a2f9dc238b41d7f8337d9bf58e578e5274ebb9566a4e'
                     if arm == 'v5' else selected['candidate_release_manifest_sha256'])
        assert meta['model_identity'] == f'student-{arm}:{model_sha}:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a'
        problem, spec = problems(root, arm, ids), specifications(root, arm)
        assert problem['protocol']['identity'] == spec['protocol']['identity'] == meta['model_identity']
        arms[arm] = {'problems': problem, 'specifications': spec, 'generation': meta}
    for panel in ('problems', 'specifications'):
        a, b = arms['v5'][panel], arms['v6'][panel]
        assert a['evaluator'] == b['evaluator'], panel+' evaluators differ'
        protocols = []
        for record in (a, b):
            protocol = {k: v for k, v in record['protocol'].items() if k not in ('model', 'identity')}
            if 'route_args' in protocol:
                protocol['route_args'] = [*protocol['route_args']]
                protocol['route_args'][1] = '<paired-tag>'
            protocols.append(protocol)
        assert protocols[0] == protocols[1], panel+' generation protocols differ'
    metadata = [{k:v for k,v in arms[a]['generation'].items() if k not in ('arm','model_identity')} for a in arms]
    assert metadata[0] == metadata[1], 'server configuration or candidate selection differs'
    counts = {a: {'one': len(r['problems']['sets']['1']), 'seven': len(r['problems']['sets']['7']),
                  'spec': len(r['specifications']['sets']['7'])} for a,r in arms.items()}
    integrity_ok = not any(values for r in arms.values() for p in ('problems','specifications')
                           for values in r[p]['integrity'].values())
    result = {'counts': counts, **decision(counts['v5'], counts['v6'], integrity_ok),
              'paired': {p: {str(k): paired(arms['v5'][p]['sets'][str(k)], arms['v6'][p]['sets'][str(k)])
                             for k in score_levels.LEVELS} for p in ('problems','specifications')},
              'details': {a: {p: {k:v for k,v in r[p].items() if k not in ('sets','protocol','evaluator')}
                              for p in ('problems','specifications')} for a,r in arms.items()},
              'same_generation_protocol': True, 'same_evaluator': True,
              'limits': 'One fixed training seed and candidate. A one-problem gain does not establish a general gain across seeds. Historical v5 used full-precision decoding and is reported separately.',
              'candidate_lock_sha256': digest(root/'candidate-frozen.json')}
    (root/'comparison.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'counts': counts, 'qualified': result['qualified'], 'checks': result['checks']}, indent=2))
    return 0 if result['qualified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
