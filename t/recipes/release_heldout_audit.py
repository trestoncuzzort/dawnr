"""Independently audit a recovered private final reading without executing answers.

Authenticate the original workflow and encrypted artifact before using this reader.
Sources: release_grade_audit.development, release_heldout_grade.validate and finish.
https://github.com/trestoncuzzort/dawnr/blob/main/t/recipes/release_grade_audit.py
"""
import hashlib
import json
from pathlib import Path
import re

import release_grade_audit as audit
import release_heldout_grade as transport

require, digest, read = audit.require, audit.digest, audit.read


def final_reading(root, original, protocol, asset_sha, workflow_revision, run_id, expected_sources):
    """Read all 182 outcomes; the numeric result still precedes laptop checks."""
    root = Path(root)
    hashes = audit.files(root)
    claim = json.loads(original['claim.json'])
    tag = claim['tag']
    validation = transport.validate(original, protocol, tag)
    saved = root/'inputs'
    require(audit.files(saved) == transport.file_hashes(original), 'saved private inputs changed')
    require(all((saved/name).read_bytes() == value for name, value in original.items()),
            'graded private inputs differ from the sealed originals')
    require(read(root/'input-validation.json') == validation, 'input validation record differs')
    receipt = read(root/'receipt.json')
    require((root/'COMPLETE').read_text().strip() == digest(root/'receipt.json'), 'final grade completion differs')
    graded = root/'v5-repair-20261021/proof-results'/tag
    require((graded/'GRADED').is_file(), 'final grade is incomplete')
    levels = read(graded/'levels.json')
    require(levels['ids'] == 182 and len(levels['rows']) == 1, 'final grade covers another panel')
    row = levels['rows'][0]
    require(row['tag'] == tag and row['problems'] == 182, 'final row identity differs')
    clean, all_seven = row['>=1'], row['>=7']
    require(type(clean) is int and type(all_seven) is int and 0 <= all_seven <= clean <= 182,
            'invalid final coverage counts')
    transport.heldout.choose.check_digest(asset_sha)
    require(re.fullmatch(r'[0-9a-f]{40}', workflow_revision) and str(run_id).isdigit(), 'invalid workflow identity')
    expected = {'kind':'private-final-grade','tag':tag,'seed':validation['seed'],
                'model_sha256':validation['model_sha256'],'panel_sha256':validation['panel_sha256'],
                'grader_revision':transport.GRADER,'workflow_revision':workflow_revision,'run_id':str(run_id),
                'input_asset_sha256':asset_sha,'input_validation_sha256':digest(root/'input-validation.json'),
                'levels_sha256':digest(graded/'levels.json'),'evaluator_sha256':digest(graded/'evaluator.json'),
                'clean':clean,'all_seven':all_seven,'required_clean':17,'required_all_seven':12,
                'meets_numeric_floors':clean>=17 and all_seven>=12,
                'independent_content_audit_pending':True,'final_laptop_checks_pending':True}
    require(receipt == expected, 'final grade receipt differs from the original handoff')
    generated = {'spec_first.json':original['spec_first.json']}
    generated.update({'raw/'+name[4:]:value for name,value in original.items() if name.startswith('raw-')})
    panel = original['panel.txt']
    require(expected_sources.get(transport.PANEL_PATH) == hashlib.sha256(panel).hexdigest(),
            'final grader panel source differs')
    content = audit.development(root, tag, panel, generated, expected_sources)
    require(content['reading']['scores'] == row, 'final grade row differs from the complete content audit')
    ids = set(map(int, transport.heldout.panel_ids(panel)))
    kept, seven = set(content['sets']['1']), set(content['sets']['7'])
    require(seven <= kept <= ids, 'confirmed final coverage leaves the registered panel')
    passes = len(kept)>=17 and len(seven)>=12
    return {'kind':'independently-audited-private-final-reading','tag':tag,'seed':validation['seed'],
            'model_sha256':validation['model_sha256'],'panel_sha256':validation['panel_sha256'],
            'workflow_revision':workflow_revision,'run_id':str(run_id),'input_asset_sha256':asset_sha,
            'receipt_sha256':digest(root/'receipt.json'),
            'choice_sha256':claim['choice_sha256'],'selection_bundle_sha256':claim['selection_bundle_sha256'],
            'reported_clean':clean,'reported_all_seven':all_seven,
            'confirmed_clean':len(kept),'confirmed_all_seven':len(seven),
            'required_clean':17,'required_all_seven':12,'meets_numeric_floors':passes,
            'status':'heldout-passed-pending-laptop' if passes else 'heldout-failed',
            'independent_content_audit_pending':False,'final_laptop_checks_pending':True,
            'publication_pending':True,'content_audit':content,'files_sha256':hashes}
