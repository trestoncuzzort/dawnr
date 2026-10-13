import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Eight findings of the GPT-6 Astra review of 2026-10-13 on the Lean adapter, each reproduced before its fix.


def test_true_is_not_a_refutation_certificate():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from subprocess import CompletedProcess
    from unittest.mock import patch
    from verifiers import lean

    src = 'theorem t_refutation_certificate : True := True.intro\n'
    out = "'t_audit_ok_0' does not depend on any axioms\n"
    out += "'t_refutation_certificate' does not depend on any axioms\n"
    with TemporaryDirectory() as d:
        p = Path(d) / 'case.lean'
        p.write_text(src, encoding='utf-8')
        with patch.object(lean.secrets, 'token_hex', return_value='0'), patch.multiple(
            lean, version=lambda: 'test',
            run_tree=lambda *a, **k: CompletedProcess([], 0, out, ''),
            Result=lambda *a, **k: a[3]
        ):
            assert lean.verify(p) != lean.Outcome.REFUTED


def test_smoke_failure_does_not_disable_certificate_coherence():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from subprocess import CompletedProcess
    from unittest.mock import patch
    from verifiers import lean

    src = ('theorem goal : True := True.intro\n'
           'theorem goal_t_vacuity_smoke : False := by omega\n'
           'theorem t_refutation_certificate : True := True.intro\n')
    out = 'error: omega could not prove the goal\n'
    out += "'t_audit_ok_0' does not depend on any axioms\n"
    out += "'goal' does not depend on any axioms\n"
    out += "'goal_t_vacuity_smoke' depends on axioms: [sorryAx]\n"
    out += "'t_refutation_certificate' does not depend on any axioms\n"
    with TemporaryDirectory() as d:
        p = Path(d) / 'case.lean'
        p.write_text(src, encoding='utf-8')
        with patch.object(lean.secrets, 'token_hex', return_value='0'), patch.multiple(
            lean, version=lambda: 'test',
            run_tree=lambda *a, **k: CompletedProcess([], 1, out, ''),
            Result=lambda *a, **k: a[3]
        ):
            assert lean.verify(p) == lean.Outcome.MALFORMED


def test_unicode_obligation_cannot_disappear_from_audit():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from subprocess import CompletedProcess
    from unittest.mock import patch
    from verifiers import lean

    src = ('theorem good : True := True.intro\n'
           'theorem α : False := by omega\n'
           'theorem good_t_vacuity_smoke : False := by omega\n')
    out = 'error: omega could not prove the goal\n'
    out += "'t_audit_ok_0' does not depend on any axioms\n"
    out += "'good' does not depend on any axioms\n"
    out += "'good_t_vacuity_smoke' depends on axioms: [sorryAx]\n"
    with TemporaryDirectory() as d:
        p = Path(d) / 'case.lean'
        p.write_text(src, encoding='utf-8')
        with patch.object(lean.secrets, 'token_hex', return_value='0'), patch.multiple(
            lean, version=lambda: 'test',
            run_tree=lambda *a, **k: CompletedProcess([], 1, out, ''),
            Result=lambda *a, **k: a[3]
        ):
            assert lean.verify(p) != lean.Outcome.VERIFIED


def test_namespace_collision_cannot_hide_failed_theorem():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from subprocess import CompletedProcess
    from unittest.mock import patch
    from verifiers import lean

    src = ('namespace A\n'
           'theorem goal : False := by omega\n'
           'end A\n'
           'namespace B\n'
           'theorem goal : True := True.intro\n'
           'theorem goal_t_vacuity_smoke : False := by omega\n'
           'end B\nopen B\n')
    out = 'error: omega could not prove the goal\n'
    out += "'t_audit_ok_0' does not depend on any axioms\n"
    out += "'B.goal' does not depend on any axioms\n"
    out += "'B.goal_t_vacuity_smoke' depends on axioms: [sorryAx]\n"
    with TemporaryDirectory() as d:
        p = Path(d) / 'case.lean'
        p.write_text(src, encoding='utf-8')
        with patch.object(lean.secrets, 'token_hex', return_value='0'), patch.multiple(
            lean, version=lambda: 'test',
            run_tree=lambda *a, **k: CompletedProcess([], 1, out, ''),
            Result=lambda *a, **k: a[3]
        ):
            assert lean.verify(p) != lean.Outcome.VERIFIED


def test_character_literals_do_not_hide_banned_commands():
    from verifiers import lean

    src = '''def q1 : Char := '"'
set_option maxHeartbeats 0
def q2 : Char := '"'
theorem good : True := True.intro
'''
    stripped = lean._strip_comments_strings(src)
    assert lean.BANNED.search(stripped) is not None


def test_verdict_hash_matches_the_source_actually_checked():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from subprocess import CompletedProcess
    from unittest.mock import patch
    from verifiers import lean

    real_hash = lean.sha256_file
    old_hashes = []
    def hash_then_replace(p):
        h = real_hash(p)
        old_hashes.append(h)
        p.write_text('theorem goal : True := True.intro\n', encoding='utf-8')
        return h

    out = "'t_audit_ok_0' does not depend on any axioms\n"
    out += "'goal' does not depend on any axioms\n"
    with TemporaryDirectory() as d:
        p = Path(d) / 'case.lean'
        p.write_text('theorem goal : False := by omega\n', encoding='utf-8')
        with patch.object(lean.secrets, 'token_hex', return_value='0'), patch.multiple(
            lean, sha256_file=hash_then_replace, version=lambda: 'test',
            run_tree=lambda *a, **k: CompletedProcess([], 0, out, ''),
            Result=lambda *a, **k: (a[2], a[3])
        ):
            result = lean.verify(p)
        assert result != (old_hashes[0], lean.Outcome.VERIFIED)


def test_audit_accepts_primed_theorem_names():
    from verifiers import lean

    line = "'good'' does not depend on any axioms"
    assert lean.AUDIT_LINE.findall(line) == [("good'", '')]


def test_theorem_name_is_not_a_timeout_diagnostic():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from subprocess import CompletedProcess
    from unittest.mock import patch
    from verifiers import lean

    out = "'t_audit_ok_0' does not depend on any axioms\n"
    out += "'maxHeartbeats_ok' does not depend on any axioms\n"
    with TemporaryDirectory() as d:
        p = Path(d) / 'case.lean'
        p.write_text('theorem maxHeartbeats_ok : True := True.intro\n', encoding='utf-8')
        with patch.object(lean.secrets, 'token_hex', return_value='0'), patch.multiple(
            lean, version=lambda: 'test',
            run_tree=lambda *a, **k: CompletedProcess([], 0, out, ''),
            Result=lambda *a, **k: a[3]
        ):
            assert lean.verify(p) == lean.Outcome.VERIFIED
