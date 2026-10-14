import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

# Seven findings of the GPT-6 Astra review of 2026-10-13 on the held-out audit, each reproduced before its fix: a CRLF fence still holds a program; a Unicode line separator inside a JSON string is one row; rows that share a basename do not merge; rewriting the wider policy keeps the unfaithful exclusions; v5 does not gate a wider-only lineage; a lineage inside the provenance key is found; an omission of another length is not discarded.


def test_crlf_fenced_program_is_audited():
    import heldout_audit as ha
    program = ('t 0\r\n'
               'task double_it(n: int) returns (r: int)\r\n'
               '  ensures r == 2 * n\r\n'
               '{\r\n  r := 2 * n;\r\n}\r\n')
    row = {'chosen': '```t\r\n' + program + '```'}
    assert ha.blocks(row) == [program]


def test_same_basename_does_not_merge_flagged_rows():
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import heldout_audit as ha
    with tempfile.TemporaryDirectory() as directory:
        paths = []
        for subdirectory in ('a', 'b'):
            path = Path(directory) / subdirectory / 'rows.jsonl'
            path.parent.mkdir()
            path.write_text(json.dumps({'name': 'dafny_synthesis_task_id_95'}) + '\n', encoding='utf-8')
            paths.append(path)
        rows = ha.read_rows(paths)
        with patch.object(ha.se, 'pool', return_value={}), \
             patch.object(ha, 'gates', return_value={95: 'dev'}), \
             patch.object(ha.twin_draws, 'runner', return_value=None):
            result = ha.audit(rows, table={}, jobs=1)
        assert len(result['flagged']) == 2
        assert ha.by_problem(result['findings'])[('dev', 95)]['rows'] == 2


def test_v5_does_not_gate_wider_only_lineage():
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import heldout_audit as ha
    with tempfile.TemporaryDirectory() as directory:
        split = Path(directory) / 'split.json'
        split.write_text(json.dumps({'eval_ids': []}), encoding='utf-8')
        with patch.object(ha.se, 'pool', return_value={}), \
             patch.object(ha.se, 'wider_pool', return_value={95: {}}), \
             patch.object(ha.loop_filter, 'r12_dev_ids', return_value=set()), \
             patch.object(ha.twin_draws, 'runner', return_value=None):
            result = ha.audit(
                [('rows.jsonl', 0, {'name': 'dafny_synthesis_task_id_95'})],
                pool_name='v5', split_path=split, table={}, jobs=1)
        assert result['findings'] == []


def test_rewriting_wider_policy_preserves_unfaithful_exclusions():
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import heldout_audit as ha
    excluded = {222, 398, 712}
    result = {'findings': [], 'flagged': [], 'rows': 1, 'programs': 0, 'unparsed': 0}
    with tempfile.TemporaryDirectory() as directory:
        rows = Path(directory) / 'rows.jsonl'
        rows.write_text(json.dumps({'name': 'unrelated'}) + '\n', encoding='utf-8')
        policy = Path(directory) / 'wider.json'
        policy.write_text(json.dumps({'schema': 1, 'flagged_ids': [],
                                      'unfaithful_ids': sorted(excluded)}), encoding='utf-8')
        with patch.object(ha, 'audit', return_value=result), \
             patch.object(ha.se, 'wider_pool', return_value={i: {} for i in excluded}):
            ha.main(['--rows', str(rows), '--write-wider-policy', str(policy)])
            assert not (ha.wider_clean(policy) & excluded)


def test_lineage_in_provenance_key_is_found():
    import heldout_audit as ha
    table = {'dd0736': {'mbpp': 474, 'via': 'MBPP-DFY',
                        'source_id': 'dafny-synthesis_task_id_474'}}
    row = {'name': 'renamed',
           'provenance': {'vericoding_dd0736__replaceChars': True}}
    assert set(ha.named_mbpp(row, table)) == {474}


def test_alternative_length_omission_is_not_discarded():
    import heldout_audit as ha
    program = ('t 1\n'
               'task append_value(a: seq, k: int) returns (r: seq)\n'
               '  ensures r == a + [k]\n'
               '{\n  r := a + [k];\n}\n')
    task = ha.surface.parse(program)
    points = [
        {'ok': True, 'fn': 'f',
         'args': [('seq', a), ('int', len(a)), ('int', len(a))],
         'expected': ('seq', a + [len(a)])}
        for a in ([10], [20, 30])
    ]
    entry = {'points': points}
    assert ha.quiet(task, ha.without_argument(points, 2)) == ['pass', 'pass']
    found = ha.candidates(task, {7: (entry, 'held-out')})
    assert [2, 0] in [candidate['dropped'] for candidate in found]


def test_unicode_line_separator_inside_json_string():
    import json
    import tempfile
    from pathlib import Path
    import heldout_audit as ha
    row = {'prompt': 'before\u2028after'}
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'rows.jsonl'
        path.write_text(json.dumps(row, ensure_ascii=False) + '\n', encoding='utf-8')
        assert ha.read_rows([path]) == [('rows.jsonl', 0, row)]
