import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Five findings of the GPT-6 Astra review of 2026-10-13 on the Rocq adapter, each reproduced before its fix.


def test_true_is_not_a_refutation_certificate():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from subprocess import CompletedProcess
    from unittest.mock import patch
    from verifiers import rocq as r

    responses = [CompletedProcess([], 0, '', ''),
                 CompletedProcess([], 0, r.CLOSED + '\n', ''),
                 CompletedProcess([], 0, '', '')]
    with TemporaryDirectory() as d:
        p = Path(d) / 'input.v'
        p.write_text('Theorem t_refutation_certificate : True. Proof. exact I. Qed.\n', encoding='utf-8')
        with (
            patch.multiple(r, COQC='coqc', COQCHK='coqchk'),
            patch.object(r.shutil, 'which', return_value='/mock/coqc'),
            patch.object(r, 'version', return_value='test'),
            patch.object(r, 'run_tree', side_effect=responses),
            patch.object(r, 'Result', side_effect=lambda *a, **kw: a[3]),
        ):
            assert r.verify(p) != r.Outcome.REFUTED


def test_nested_obligation_is_not_hidden_by_same_basename():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from subprocess import CompletedProcess
    from unittest.mock import patch
    from verifiers import rocq as r

    source = ('From Stdlib Require Import Logic.Classical_Prop.\n'
              'Theorem goal : True. Proof. exact I. Qed.\n'
              'Module M.\n'
              'Theorem goal : forall P : Prop, or P (not P). Proof. exact classic. Qed.\n'
              'End M.\n')
    responses = [CompletedProcess([], 0, '', ''),
                 CompletedProcess([], 0, r.CLOSED + '\n', ''),
                 CompletedProcess([], 0, 'CONTEXT SUMMARY\nAxioms:\n  Stdlib.Logic.Classical_Prop.classic\n', '')]
    with TemporaryDirectory() as d:
        p = Path(d) / 'input.v'
        p.write_text(source, encoding='utf-8')
        with (
            patch.multiple(r, COQC='coqc', COQCHK='coqchk'),
            patch.object(r.shutil, 'which', return_value='/mock/coqc'),
            patch.object(r, 'version', return_value='test'),
            patch.object(r, 'run_tree', side_effect=responses),
            patch.object(r, 'Result', side_effect=lambda *a, **kw: a[3]),
        ):
            assert r.verify(p) != r.Outcome.VERIFIED


def test_result_hash_matches_the_compiled_snapshot():
    import hashlib
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from subprocess import CompletedProcess
    from unittest.mock import patch
    from verifiers import rocq as r

    real_hash = r.sha256_file
    compiled_hashes = []

    def hash_then_replace(path):
        digest = real_hash(path)
        path.write_text('Theorem goal : True. Proof. exact I. Qed.\n', encoding='utf-8')
        return digest

    def kernel(argv, **kw):
        if argv[1] == 't_unit.v':
            data = (Path(kw['cwd']) / 't_unit.v').read_bytes()
            compiled_hashes.append(hashlib.sha256(data).hexdigest())
        stdout = r.CLOSED + '\n' if argv[1] == 't_audit.v' else ''
        return CompletedProcess(argv, 0, stdout, '')

    with TemporaryDirectory() as d:
        p = Path(d) / 'input.v'
        p.write_text('Theorem goal : False. Proof. exact I. Qed.\n', encoding='utf-8')
        with (
            patch.multiple(r, COQC='coqc', COQCHK='coqchk'),
            patch.object(r.shutil, 'which', return_value='/mock/coqc'),
            patch.object(r, 'version', return_value='test'),
            patch.object(r, 'sha256_file', side_effect=hash_then_replace),
            patch.object(r, 'run_tree', side_effect=kernel),
            patch.object(r, 'Result', side_effect=lambda *a, **kw: a[2]),
        ):
            reported_hash = r.verify(p)
        assert reported_hash == compiled_hashes[0]


def test_incomplete_proof_is_unproved():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from subprocess import CompletedProcess
    from unittest.mock import patch
    from verifiers import rocq as r

    failure = CompletedProcess([], 1, '', 'Error: (in proof goal): Attempt to save an incomplete proof\n')
    with TemporaryDirectory() as d:
        p = Path(d) / 'input.v'
        p.write_text('Theorem goal : False. Proof. auto. Qed.\n', encoding='utf-8')
        with (
            patch.object(r, 'COQC', 'coqc'),
            patch.object(r.shutil, 'which', return_value='/mock/coqc'),
            patch.object(r, 'version', return_value='test'),
            patch.object(r, 'run_tree', return_value=failure),
            patch.object(r, 'Result', side_effect=lambda *a, **kw: a[3]),
        ):
            assert r.verify(p) == r.Outcome.UNPROVED


def test_apostrophe_identifier_is_not_a_banned_token():
    from verifiers import rocq as r
    source = "Lemma admit' : True. Proof. exact I. Qed.\n"
    assert r.BANNED.search(r._strip(source)) is None
