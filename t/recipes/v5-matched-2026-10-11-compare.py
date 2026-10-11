#!/usr/bin/env python3
"""Audit the completed, fixed October 11 Q8 comparison; no inference.

Run from the repository root after both grading recipes finish. This composes
score_levels.tag_levels, score_spec_given.level_of and spec_check.complete:
https://github.com/trestoncuzzort/dawnr/blob/0683081c/t/score_levels.py
"""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, 't')
import score_heldout, score_levels, score_spec_given, spec_check, spec_experiment
root = Path('t/out/v5-matched-20261011')
expected = {int(i) for i in (root/'clean-200.txt').read_text().split()}
assert len(expected) == 200
panels = {p: score_levels.panel_ids(Path('t/out/loop/split-v5.json'), p, None)
          for p in ('clean-200','clean-182')}
assert panels['clean-200'] == expected
arms = {}
for arm in ('v5','recovered'):
    out = root/arm
    assert (out/'GRADED').exists(), arm+' incomplete'
    tag = 'v5-matched-20261011-'+arm
    d = Path('t/out/spec-experiment')/tag
    raw = {int(p.stem):json.loads(p.read_text()) for p in (d/'raw').glob('*.json')}
    assert set(raw) == expected
    ext = json.loads((d/'extract.json').read_text())
    tests = json.loads((d/'tests.json').read_text())
    columns,cells = spec_experiment.parse_kernel_table(d/'kernels.md')
    names = {json.loads(p.read_text())['name'] for p in (d/'tasks').glob('*.json')}
    assert set(columns)==set(spec_check.KERNELS) and set(cells)==names
    verdicts = json.loads((out/'verdicts.json').read_text())['results']
    assert set(verdicts)=={tag+'/'+n for n in names}
    levels = score_levels.tag_levels(tag,expected,verdicts,0.6,True)
    coverage = {}
    for tid,values in levels.items():
        if not values[0]: continue
        name = ext[str(tid)]['name']
        r = verdicts[tag+'/'+name]; larger=r.get('larger') or {}
        coverage[tid] = {'name':name,'level':values[0],'ordinary_draws':r.get('draws'),
                         'ordinary_complete':spec_check.complete(r,0.6),
                         'larger_status':larger.get('status'),'larger_draws':larger.get('draws',0),
                         'larger_complete':spec_check.complete(larger,0.6)}
    # The registration refuses unknown evidence. Retain the legacy scorer's
    # raw counts too if an admission relies on an unmeasured completeness check.
    confirmed = {i for i,c in coverage.items() if c['ordinary_complete'] is True
                 and c['larger_status']=='agrees' and c['larger_draws']>=spec_check.MIN_LARGER
                 and c['larger_complete'] is True}
    for panel in panels:
        filename = 'problem-levels-200.json' if panel == 'clean-200' else 'problem-levels.json'
        saved = json.loads((out/filename).read_text())
        rows, pooled = score_levels.table([tag],panels[panel],verdicts,0.6,True)
        assert saved == {'rows':rows,'pooled':pooled,'ids':len(panels[panel])}, (arm,panel,'score changed')
    spec_report = json.loads((out/'spec-report.json').read_text())
    _,spec_cells = spec_experiment.parse_kernel_table(out/'spec-kernels.md')
    question_names={json.loads(l)['name'] for l in (out/'spec-heldout.jsonl').read_text().splitlines()}
    assert len(question_names)==33 and set(spec_report['entries'])==question_names
    spec_levels={n:score_spec_given.level_of(spec_cells.get(n))[1] if e['stage']=='ready' else 0
                 for n,e in spec_report['entries'].items()}
    saved_spec = json.loads((out/'spec-levels.json').read_text())
    assert saved_spec['proved by all seven'] == sum(v == 7 for v in spec_levels.values())
    arms[arm]={'raw':raw,'levels':levels,'confirmed':confirmed,'coverage':coverage,
               'spec_levels':spec_levels,'evaluator':json.loads((out/'evaluator.json').read_text()),
               'summary':{'program_tasks':len(names),'verdict_entries':len(verdicts),
                          'contradictions':[n for n,row in cells.items() if {'verified','refuted'} <= {v.split(' / ')[0] for v in row.values()}],
                          'unsound_cells':[[n,k] for n,row in cells.items() for k,v in row.items() if v.endswith(' / unsound')],
                          'spec_contradictions':[n for n,row in spec_cells.items() if {'verified','refuted'} <= {v.split(' / ')[0] for v in row.values()}],
                          'spec_unsound_cells':[[n,k] for n,row in spec_cells.items() for k,v in row.items() if v.endswith(' / unsound')],
                          'admitted_coverage':coverage,'unconfirmed_admissions':sorted(set(coverage)-confirmed)}}
assert (root/'v5/spec-heldout.jsonl').read_bytes() == (root/'recovered/spec-heldout.jsonl').read_bytes()
assert arms['v5']['evaluator']==arms['recovered']['evaluator'], 'evaluators differ'
program_evaluators = [json.loads((root/a/'program-evaluator.json').read_text()) for a in arms]
assert program_evaluators[0] == program_evaluators[1], 'programming wrappers differ'
assert program_evaluators[0]['lowering_address_space_mib'] == 4096
for path, sha in program_evaluators[0]['files'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha, path+' changed'
for i in expected:
    a,b=arms['v5']['raw'][i],arms['recovered']['raw'][i]
    for key in ('messages','options','pool_version','prompt_version'):
        assert a[key]==b[key], (i,key)
    assert a['prompt_version']=='s2' and a['options']['temperature']==0
    assert a['options']['num_predict']==1024
assert set(arms['v5']['spec_levels'])==set(arms['recovered']['spec_levels'])

def pair(a,b):
    return {'v5':len(a),'recovered':len(b),'gained':sorted(b-a),'lost':sorted(a-b),'both':sorted(a&b),'difference':len(b)-len(a)}
result={'method':['score_levels.tag_levels','score_spec_given.level_of','spec_check.complete'],
        'same_evaluator':True,'same_problem_requests':True,
        'arms':{a:r['summary'] for a,r in arms.items()},'panels':{}}
for panel,ids in panels.items():
    result['panels'][panel]={'questions':len(ids),'levels':{}}
    for k in score_levels.LEVELS:
        raw_sets={a:{i for i in ids if r['levels'][i][0]>=k} for a,r in arms.items()}
        sets={a:raw_sets[a]&r['confirmed'] for a,r in arms.items()}
        result['panels'][panel]['levels'][str(k)]={'registered_scorer':pair(raw_sets['v5'],raw_sets['recovered']),
                                                  'confirmed_evidence':pair(sets['v5'],sets['recovered'])}
result['specifications']={'questions':33,'known_training_overlap_in_v5':19,'levels':{}}
for k in score_levels.LEVELS:
    sets={a:{n for n,v in r['spec_levels'].items() if v>=k} for a,r in arms.items()}
    result['specifications']['levels'][str(k)]=pair(sets['v5'],sets['recovered'])
pdiff=result['panels']['clean-182']['levels']['7']['confirmed_evidence']['difference']
sdiff=result['specifications']['levels']['7']['difference']
result.update(prediction_M1_holds=not(pdiff>0 and sdiff>0),measured_win=pdiff>0 and sdiff>=0,
              qualification='One fixed candidate on previously used panels; the full 33 include 19 known v5 training-overlap functions. This does not reproduce the historical 17-call route.')
files=[Path('t/recipes/v5-matched-2026-10-11-compare.py'),root/'environment.json',root/'server-parity.json',root/'clean-200.txt']
for arm in arms:
    files += [root/arm/n for n in ('program-evaluator.json','spec-answers.jsonl','spec-kernels.md','spec-levels.json','verdicts.json','problem-levels.json','problem-levels-200.json')]
    files += [Path('t/out/spec-experiment')/('v5-matched-20261011-'+arm)/'kernels.md']
result['evidence_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(root/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('arms','evidence_sha256')},indent=2))
