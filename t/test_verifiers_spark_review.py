import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Seven findings of the GPT-6 Astra review of 2026-10-13 on the SPARK adapter, each reproduced before its fix. The
# eighth (an unrelated pending check beside a proved certificate) keeps the original coherence gate: a pending
# check means the kernel did not prove the twin, so the certificate stands; see TRIAGE.md.


def test_helper_post_does_not_establish_f_theorem():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from verifiers import spark as s
    data = {
        'entities': {
            '1': {'name': 'P.F', 'sloc': [{'file': 'p.ads'}]},
            '2': {'name': 'P.Helper', 'sloc': [{'file': 'p.ads'}]}},
        'spark': {'1': 'all', '2': 'all'},
        'proof': [{'entity': 2, 'rule': 'VC_POSTCONDITION',
                   'severity': 'info', 'file': 'p.ads', 'line': 4}]}
    with TemporaryDirectory() as td:
        work = Path(td)
        (work / 'gnatprove').mkdir()
        (work / 'gnatprove' / 'p.spark').write_text(json.dumps(data))
        audit, why = s._read_audit(work)
    assert audit is not None, why
    assert not audit['f_post']
    assert s._classify_audit(audit)[0] == s.Outcome.MALFORMED


def test_failed_escalation_cannot_verify():
    from types import SimpleNamespace
    from unittest.mock import patch
    from verifiers import spark as s
    original = {'unproved': [
        {'rule': 'VC_SUBPROGRAM_VARIANT', 'status': 'gave_up'}]}
    clean = dict(proved=1, post_proved=1, justified=0, unproved=[],
                 skips=0, assumes=0, entities={'p:1': 'all'},
                 contradictory=[], unreachable=[], f_post=['info/None'],
                 cert={'proved': 0, 'post_proved': 0, 'unproved': []})
    failed = SimpleNamespace(returncode=1, stdout='',
                             stderr='p.ads:9:1: error: invalid declaration\n')
    with patch.object(s, '_run', return_value=(failed, clean, '')):
        outcome, _ = s._escalate_variant_timeout(
            'package P is end P;', 'p.ads', original,
            s.Outcome.TIMEOUT, 'budget exhausted')
    assert outcome in (s.Outcome.TIMEOUT, s.Outcome.MALFORMED,
                       s.Outcome.TOOL_ERROR)


def test_escalated_result_records_decisive_run():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace
    from unittest.mock import patch
    from verifiers import spark as s
    def audit(post_status):
        checks = [dict(how='prover', rule=rule, severity='medium',
                       status=status, cntexmp=False, at='p.ads:3')
                  for rule, status in [
                      ('VC_SUBPROGRAM_VARIANT', 'gave_up'),
                      ('VC_POSTCONDITION', post_status)]]
        return dict(proved=0, post_proved=0, justified=0, unproved=checks,
                    skips=0, assumes=0, entities={'p:1': 'all'},
                    contradictory=[], unreachable=[],
                    f_post=['medium/' + post_status],
                    cert={'proved': 0, 'post_proved': 0, 'unproved': []})
    first, second = audit('limit'), audit('gave_up')
    proc = SimpleNamespace(returncode=0, stdout='', stderr='')
    with TemporaryDirectory() as td:
        path = Path(td) / 'p.ads'
        path.write_text('package P is end P;\n')
        with patch.object(s, 'GNATPROVE', 'gnatprove'), \
             patch.object(s, 'version', return_value='test'), \
             patch.object(s, '_run', side_effect=[
                 (proc, first, ''), (proc, second, '')]):
            result = s.verify(path, budget=s.DEFAULT_STEPS)
    assert f'steps={s.ESCALATED_STEPS}' in result.budget
    assert result.extras['unproved'] == second['unproved']


def test_package_comment_does_not_choose_filename():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from unittest.mock import patch
    from verifiers import spark as s
    source = ("-- package Old_Name\n"
              "package P with SPARK_Mode is\n"
              "  function F return Integer with Post => F'Result = 0;\n"
              "  function F return Integer is (0);\n"
              "end P;\n")
    with TemporaryDirectory() as td:
        path = Path(td) / 'p.ads'
        path.write_text(source)
        with patch.object(s, 'GNATPROVE', 'gnatprove'), \
             patch.object(s, 'version', return_value='test'), \
             patch.object(s, '_run', return_value=(None, None, 'timeout')) as run:
            s.verify(path)
    assert run.call_args.args[1] == 'p.ads'


def test_error_unit_name_is_not_error_severity():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace
    from unittest.mock import patch
    from verifiers import spark as s
    check = dict(how='prover', rule='VC_POSTCONDITION', severity='high',
                 status='gave_up', cntexmp=True, at='error.ads:2')
    audit = dict(proved=0, post_proved=0, justified=0, unproved=[check],
                 skips=0, assumes=0, entities={'error:1': 'all'},
                 contradictory=[], unreachable=[], f_post=['high/gave_up'],
                 cert={'proved': 0, 'post_proved': 0, 'unproved': []})
    proc = SimpleNamespace(returncode=0, stderr='', stdout=
                           'error.ads:2:53: high: postcondition might fail\n')
    source = ("package Error with SPARK_Mode is\n"
              "  function F return Integer with Post => F'Result = 1;\n"
              "  function F return Integer is (0);\n"
              "end Error;\n")
    with TemporaryDirectory() as td:
        path = Path(td) / 'error.ads'
        path.write_text(source)
        with patch.object(s, 'GNATPROVE', 'gnatprove'), \
             patch.object(s, 'version', return_value='test'), \
             patch.object(s, '_run', return_value=(proc, audit, '')):
            result = s.verify(path)
    assert result.outcome == s.Outcome.REFUTED


def test_import_identifier_is_not_import_aspect():
    from verifiers import spark as s
    source = ("package P with SPARK_Mode is\n"
              "  Import : constant Integer := 0;\n"
              "  function F return Integer with Post => F'Result = 0;\n"
              "  function F return Integer is (Import);\n"
              "end P;\n")
    assert s.BANNED.search(s._active_code(source)) is None


def test_sparklib_second_in_with_clause():
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch
    from verifiers import spark as s
    source = ('with Ada.Numerics.Big_Numbers.Big_Integers, '
              'SPARK.Containers.Functional.Infinite_Sequences;\n'
              'package P with SPARK_Mode is end P;\n')
    def fake_run(cmd, **kwargs):
        project = (Path(kwargs['cwd']) / 't_work.gpr').read_text()
        assert 'with "sparklib";' in project
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    with patch.object(s, 'run_tree', side_effect=fake_run):
        s._run(source, 'p.ads', 100, warnings=False)
