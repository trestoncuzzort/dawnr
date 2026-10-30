"""Full private zero-reading and forged-result controls; no program is executed."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parent/'recipes'))
import complete_empty_grade as empty
import release_heldout_audit as final
from test_release_heldout_grade import payload, prepared, completed, archive, write


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('final content audit must not execute a model, answer, reference or prover')
    monkeypatch.setattr(subprocess,'run',forbidden)
    monkeypatch.setattr(final.audit.spec_ceiling,'judge',forbidden)
    monkeypatch.setattr(final.audit.pair.spec_check,'check_task',forbidden)
    monkeypatch.setattr(final.audit.pair.se,'run_point',forbidden)


@pytest.fixture
def zero(payload,tmp_path,monkeypatch):
    original,protocol,tag=payload
    checkout=tmp_path/'grader'
    final.transport.prepare(archive(tmp_path/'input.tar.gz',original),checkout,protocol,tag)
    source=checkout/'t/out/spec-experiment'/tag
    (source/'tasks').mkdir();write(source/'extract.json',{});write(source/'tests.json',{})
    root=checkout/final.transport.OUTPUT_PATH
    graded=root/'v5-repair-20261021/proof-results'/tag;graded.mkdir(parents=True)
    panel=checkout/final.transport.PANEL_PATH
    sources={final.transport.PANEL_PATH:final.digest(panel),
             't/recipes/complete_empty_grade.py':final.digest(Path(empty.__file__))}
    sources.update({'t/'+Path(module.__file__).name:final.digest(Path(module.__file__))
                    for module in [final.audit.pair.se,final.audit.pair.score_levels,final.audit.pair.spec_check]})
    write(graded/'evaluator.json',sources)
    monkeypatch.setattr(empty.se,'OUT_ROOT',checkout/'t/out/spec-experiment')
    assert empty.complete(tag,panel,graded)
    final.transport.finish(checkout,tag,'a'*64,'b'*40,123)
    return (root,original,protocol,'a'*64,'b'*40,123,sources),graded


def rebound_receipt(root,**changes):
    value=final.read(root/'receipt.json');value.update(changes)
    write(root/'receipt.json',value);(root/'COMPLETE').write_text(final.digest(root/'receipt.json')+'\n')


def test_complete_zero_result_fails_the_gate_without_losing_its_evidence(zero):
    args,_=zero;value=final.final_reading(*args)
    assert value['status']=='heldout-failed'
    assert value['confirmed_clean']==value['confirmed_all_seven']==0
    assert value['content_audit']['panel_problems']==182
    assert value['independent_content_audit_pending'] is False
    assert value['final_laptop_checks_pending'] and value['publication_pending']


@pytest.mark.parametrize('change',['model','seed','workflow','run','asset','floor','pending','complete','input','validation','grader','source'])
def test_rebinding_a_bad_receipt_does_not_bypass_content_checks(zero,change):
    args,graded=zero;root=args[0]
    if change=='model':rebound_receipt(root,model_sha256='c'*64)
    elif change=='seed':rebound_receipt(root,seed=2)
    elif change=='workflow':rebound_receipt(root,workflow_revision='c'*40)
    elif change=='run':rebound_receipt(root,run_id='999')
    elif change=='asset':rebound_receipt(root,input_asset_sha256='c'*64)
    elif change=='floor':rebound_receipt(root,required_clean=0)
    elif change=='pending':rebound_receipt(root,independent_content_audit_pending=False)
    elif change=='complete':(root/'COMPLETE').write_text('0'*64)
    elif change=='input':(root/'inputs/scored-specs.jsonl').write_text('changed')
    elif change=='validation':
        write(root/'input-validation.json',{})
        rebound_receipt(root,input_validation_sha256=final.digest(root/'input-validation.json'))
    elif change=='grader':(graded/'GRADED').unlink()
    else:
        write(graded/'evaluator.json',{})
        rebound_receipt(root,evaluator_sha256=final.digest(graded/'evaluator.json'))
    with pytest.raises(ValueError):final.final_reading(*args)


def test_forged_passing_counts_with_matching_hashes_are_rejected(zero):
    args,graded=zero;levels=final.read(graded/'levels.json')
    levels['rows'][0].update({'>=1':17,'>=7':12});write(graded/'levels.json',levels)
    rebound_receipt(args[0],levels_sha256=final.digest(graded/'levels.json'),clean=17,all_seven=12,meets_numeric_floors=True)
    with pytest.raises(SystemExit,match='levels.json does not match a recomputation'):
        final.final_reading(*args)


def test_unconfirmed_answers_do_not_satisfy_final_floors(zero,monkeypatch):
    args,graded=zero
    content=final.final_reading(*args)['content_audit']
    levels=final.read(graded/'levels.json');levels['rows'][0].update({'>=1':17,'>=7':12})
    write(graded/'levels.json',levels)
    rebound_receipt(args[0],levels_sha256=final.digest(graded/'levels.json'),clean=17,all_seven=12,meets_numeric_floors=True)
    # Exercise this wrapper's contract with the existing independent content
    # reader: one reported admission is unconfirmed at each threshold.
    content=deepcopy(content);content['reading']['scores']=levels['rows'][0]
    content['sets']['1']=list(range(1000,1016));content['sets']['7']=list(range(1000,1011))
    monkeypatch.setattr(final.audit,'development',lambda *unused:content)
    result=final.final_reading(*args)
    assert result['reported_clean']==17 and result['confirmed_clean']==16
    assert result['reported_all_seven']==12 and result['confirmed_all_seven']==11
    assert result['status']=='heldout-failed' and not result['meets_numeric_floors']
