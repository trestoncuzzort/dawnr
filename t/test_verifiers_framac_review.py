import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Negative controls for the Frama-C adapter review of 2026-10-13.


def test_unrelated_named_assertion_cannot_refute():
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    from verifiers import framac as f

    src = r'''/*@ requires n >= 0;
      ensures \exists integer a, b, c, d;
        n == a*a + b*b + c*c + d*d;
    */
    void squares(int n) {}
    void t_certificate(void) {
      /*@ assert t_refutation_certificate: 1 == 1; */
    }
    '''
    report = [
        dict(goal=f.GOAL_PREFIX + 'squares_ensures', function='squares', passed=False, verdict='stepout'),
        dict(goal=f.GOAL_PREFIX + 't_certificate_assert_' + f.CERT_NAME, function='t_certificate', passed=True, verdict='valid'),
    ] + [dict(goal=f.GOAL_PREFIX + n + '_wp_smoke_default_requires', function=n, smoke=True, passed=True)
         for n in ('squares', 't_certificate')]

    def run(cmd, wall):
        if '-print' in cmd:
            return 0, f._PRINT_MARK + '\n' + src
        return 0, '[wp] Proved goals: 3 / 4\n  Smoke Tests: 2 / 2\n'

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'test.c'
        p.write_text(src)
        with patch.object(f, 'FRAMAC', 'frama-c'), patch.object(f, '_ver', return_value='test'), patch.object(f, '_run', side_effect=run), patch.object(f, '_load_report', return_value=report), patch.object(f, 'Result') as result:
            f.verify(p)
            assert result.call_args.args[3] != f.Outcome.REFUTED


def test_function_name_cannot_hide_precondition_vacuity():
    from verifiers import framac as f
    prop = 'f_wp_smoke_dead_code_wp_smoke_default_requires'
    goal = f.GOAL_PREFIX + prop
    report = [dict(goal=goal, property=prop, function='f_wp_smoke_dead_code', smoke=True, passed=False)]
    out = '[wp] [Failed] (Doomed) ' + goal + '\n[wp] Proved goals: 2 / 3\n  Smoke Tests: 0 / 1\n'
    is_vacuity, _ = f._vacuity_smoke(out, report)
    assert is_vacuity


def test_probe_marker_and_tautology_cannot_admit_inconsistent_logic():
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    from verifiers import framac as f

    src = r'''/* t_vacuity_probe */
    /*@ logic integer bad(integer n) = bad(n) + 1;
        lemma bad_terminates_0: \true;
    */
    /*@ ensures bad(x) >= 0 ==> \result == 998; */
    int target(int x) { return 999; }
    '''
    report = [
        dict(goal='lemma_bad_terminates_0', passed=True, verdict='valid'),
        dict(goal=f.GOAL_PREFIX + 'target_ensures', function='target', passed=True, verdict='valid'),
        dict(goal=f.GOAL_PREFIX + 'target_wp_smoke_default_requires', function='target', smoke=True, passed=True),
    ]

    def run(cmd, wall):
        if '-print' in cmd:
            return 0, f._PRINT_MARK + '\n' + src
        if '-wp-fct' in cmd:
            doomed = ''.join('[wp] [Failed] (Doomed) ' + f.GOAL_PREFIX + 't_vacuity_probe_' + side + '_0_wp_smoke_default_requires\n' for side in ('pos', 'neg'))
            return 0, doomed + '[wp] Proved goals: 0 / 2\n'
        return 0, '[wp] Proved goals: 3 / 3\n  Smoke Tests: 1 / 1\n'

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'test.c'
        p.write_text(src)
        with patch.object(f, 'FRAMAC', 'frama-c'), patch.object(f, '_ver', return_value='test'), patch.object(f, '_run', side_effect=run), patch.object(f, '_load_report', return_value=report), patch.object(f, 'Result') as result:
            f.verify(p)
            assert result.call_args.args[3] != f.Outcome.VERIFIED


def test_c_string_is_not_an_acsl_axiom():
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    from verifiers import framac as f

    src = r'''const char *message = "axiom";
    /*@ ensures \result == 0; */
    int target(void) { return 0; }
    '''

    def run(cmd, wall):
        if '-print' in cmd:
            return 0, f._PRINT_MARK + '\n' + src
        return 0, '[wp] Proved goals: 2 / 2\n  Smoke Tests: 1 / 1\n'

    report = [dict(goal='target_ensures', function='target', passed=True, verdict='valid'), dict(goal='target_smoke', function='target', smoke=True, passed=True)]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'test.c'
        p.write_text(src)
        with patch.object(f, 'FRAMAC', 'frama-c'), patch.object(f, '_ver', return_value='test'), patch.object(f, '_run', side_effect=run), patch.object(f, '_load_report', return_value=report), patch.object(f, 'Result') as result:
            f.verify(p)
            assert result.call_args.args[3] != f.Outcome.VACUOUS
