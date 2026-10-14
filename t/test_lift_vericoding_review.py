import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Seven findings of the review on the vericoding lift: a Lean parser refusal is a named difference, not an unchanged specification; a helper the contract refers to is compared too; normalisation keeps string literals; a resumed lift of a now-refused id is excluded; record_grades invents no pass when the check stage did not run; a failed regrade clears the earlier clean counts; the heads cache cannot alias a released dict.


def test_lean_comparison_refusal_is_not_unchanged():
    from types import SimpleNamespace
    from unittest.mock import patch
    import lift_vericoding as m

    class Refusal(Exception):
        pass

    solution = 'def f_postcond (r : Int) : Prop := True'
    reference = 'def f_postcond (r : Int) : Prop := r = 1'
    parsed = SimpleNamespace(defs={}, theorems={})
    with patch.object(m.lift_lean, 'LeanRefusal', Refusal), \
         patch.object(m.lift_lean, 'sections', return_value={}), \
         patch.object(m.lift_lean, 'parse_file', side_effect=[parsed, Refusal('unsupported reference specification')]):
        assert m.spec_changed(solution, reference, 'lean') is not None


def test_verus_contract_helper_cannot_be_weakened():
    import lift_vericoding as m

    reference = '''// <vc-preamble>
use vstd::prelude::*;
verus! {
// </vc-preamble>
// <vc-helpers>
spec fn wanted(r: int) -> bool { r == 1 }
// </vc-helpers>
// <vc-spec>
fn answer() -> (r: i32)
    ensures wanted(r as int),
// </vc-spec>
// <vc-code>
{ 1 }
// </vc-code>
// <vc-postamble>
}
// </vc-postamble>
'''
    solution = reference.replace('r == 1', 'r == 0 || r == 1').replace('{ 1 }', '{ 0 }')
    assert m.spec_changed(solution, reference, 'verus') is not None


def test_normalization_preserves_literal_contents():
    import lift_vericoding as m

    pairs = [('a  b', 'a b'), ('a--original', 'a--changed')]
    for before, after in pairs:
        a = f'def p_postcond (r : String) : Prop := r = "{before}"'
        b = f'def p_postcond (r : String) : Prop := r = "{after}"'
        assert m._norm(a, 'lean') != m._norm(b, 'lean')


def test_resume_excludes_newly_refused_artifacts():
    import json
    from collections import Counter
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace
    from unittest.mock import patch
    import lift_vericoding as m

    with TemporaryDirectory() as d:
        root = Path(d)
        out = root / 'out'
        meta = root / 'out.meta'
        (meta / 'staged').mkdir(parents=True)
        (meta / 'lift').mkdir()
        (meta / 'staged' / 'vericoding_LA0001.dfy').write_text('method answer() {}')
        task_file = meta / 'lift' / 'vericoding_LA0001.answer.json'
        task = {'name': 'answer'}
        task_file.write_text(json.dumps(task))
        args = SimpleNamespace(language='lean', out=str(out), vericoding=str(root / 'src'),
                               split='split.json', pool='v5', resume=True, jobs=1,
                               native_jobs=1, with_check=False, dedupe_against=[])
        refusal = {'id': 'LA0001', 'stage': 'select', 'reason': 'listed in lean_issues.jsonl'}
        gates = SimpleNamespace(held_out=set(), dev=set())
        with patch.object(m.lift_corpora, 'load_gating', return_value=(gates, [], {})), \
             patch.object(m, 'benchmark_rows', return_value={}), \
             patch.object(m, 'task_rows', return_value={}), \
             patch.object(m, 'select', return_value=([], [refusal], Counter(files=1))), \
             patch.object(m.lift_corpora, 'run_lifter', return_value={}), \
             patch.object(m.lift_corpora, 'refusals', return_value=Counter()), \
             patch.object(m.lift_corpora, 'lifted_tasks', return_value=[(task_file, task, {})]), \
             patch.object(m.loop_filter, 'TrainingDataGate', return_value=None), \
             patch.object(m.lift_corpora, 'hung_path_for', return_value=root / 'hung.jsonl'), \
             patch.object(m.twin_draws, 'runner', return_value=None):
            assert m.build(args)['accepted'] == 0


def test_record_grades_does_not_invent_a_pass():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from unittest.mock import patch
    import lift_vericoding as m
    import loop_locallm

    with TemporaryDirectory() as d:
        out = Path(d) / 'tasks'
        meta = Path(d) / 'tasks.meta'
        meta.mkdir()
        trust = meta / 'trust.jsonl'
        trust.write_text(json.dumps({'name': 'f', 'task_file': 'f.json',
                                     'lifter_check': 'not run here (queue step reruns it)'}) + '\n')
        with patch.object(loop_locallm, 'table_rows', return_value={}):
            m.record_grades(out, Path(d) / 'table.md')
        record = json.loads(trust.read_text())
        assert record['lifter_check'] != 'passed'


def test_failed_regrade_clears_previous_clean_count():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from unittest.mock import patch
    import lift_vericoding as m
    import loop_locallm

    with TemporaryDirectory() as d:
        root = Path(d)
        out = root / 'tasks'
        meta = root / 'tasks.meta'
        meta.mkdir()
        failed = root / 'check-failed'
        failed.mkdir()
        (failed / 'f.json').write_text('{}')
        trust = meta / 'trust.jsonl'
        trust.write_text(json.dumps({'name': 'f', 'task_file': 'f.json',
                                     'lifter_check': 'passed', 'clean_in': 7,
                                     'not_clean': []}) + '\n')
        with patch.object(loop_locallm, 'table_rows', return_value={}):
            m.record_grades(out, root / 'table.md', failed)
        record = json.loads(trust.read_text())
        assert record.get('clean_in', 0) == 0


def test_heads_cache_does_not_alias_released_inputs():
    from unittest.mock import patch
    import lift_vericoding as m

    with patch.object(m, '_HEADS_CACHE', {}):
        for n in range(1000):
            trows = {'LA0001': {'source': 'clever', 'source-id': f'clever_{n}'}}
            fixed = m.trows_for_heads(trows, {})
            assert fixed['LA0001']['source-id'] == f'humaneval_{n:03d} (clever_{n})'
            del trows
