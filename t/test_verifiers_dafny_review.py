import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Three findings of the GPT-6 Astra review of 2026-10-13 on the Dafny adapter, each reproduced before its fix.


def test_expect_is_an_unchecked_assumption():
    from verifiers.dafny import BANNED_RE
    source = '''method M(x: int) returns (r: int)
  ensures r == x
{
  r := 0;
  expect x == 0;
}
'''
    assert BANNED_RE.search(source) is not None, 'expect must be banned alongside assume'


def test_incomplete_main_cannot_authorize_refutation():
    from pathlib import Path
    from subprocess import CompletedProcess
    from unittest.mock import patch
    import t.verifiers.dafny as d

    rprint = '''method M()
{
}
lemma t_refutation_certificate()
  ensures true
{
}
'''
    incomplete_main = ('Results for t_refutation_certificate (correctness)\n'
                       '  Overall outcome: Correct\n')
    isolated_out = incomplete_main + 'Dafny program verifier finished with 1 verified, 0 errors\n'
    isolated = CompletedProcess(['dafny'], 0, isolated_out, '')
    with patch.object(d, '_solver_args', return_value=[]), \
         patch.object(d, 'run_tree', return_value=isolated):
        accepted, detail = d._check_certificate(
            Path('task.dfy'), 500000, [], incomplete_main, 0, rprint)
    assert not accepted, detail


def test_edit_between_screening_and_kernel_read_cannot_prove_original():
    from pathlib import Path
    from subprocess import CompletedProcess
    from tempfile import TemporaryDirectory
    from unittest.mock import patch
    import t.verifiers.dafny as d

    with TemporaryDirectory() as directory:
        path = Path(directory) / 'task.dfy'
        original = 'method M() ensures false {}\n'
        replacement = 'method M() ensures true {}\n'
        path.write_text(original, encoding='utf-8')

        def kernel_read(argv, **kwargs):
            # An editor saves the replacement before the child opens its input.
            path.write_text(replacement, encoding='utf-8')
            checked_source = Path(argv[-1]).read_text(encoding='utf-8')
            proved = checked_source == replacement
            tally = ('1 verified, 0 errors' if proved else '0 verified, 1 error')
            return CompletedProcess(
                argv, 0 if proved else 4,
                'Dafny program verifier finished with ' + tally + '\n', '')

        with patch.object(d, 'DAFNY', 'dafny'), \
             patch.object(d, '_solver_args', return_value=[]), \
             patch.object(d, 'version', return_value='dafny test'), \
             patch.object(d, 'run_tree', side_effect=kernel_read):
            result = d.verify(path)

        assert not result.ok, 'replacement proof was attached to the original source hash'
