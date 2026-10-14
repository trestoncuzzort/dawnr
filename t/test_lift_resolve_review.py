"""Two findings of the GPT-6 Astra review of 2026-10-13 on the Dafny lifter's
resolution pass (t/lift_resolve.py), each reproduced before its fix: a method
name declared in a second scope must not let one declaration's clauses overwrite
another's, and a loop the structural walker ignores (inside an `assert ... by
{}` block) must not let a changed invariant be retained on a warning. The fix in
both cases is a named refusal, per this repository's rule 2: an honest refusal
beats a false verdict. See the receipt (DafnyRef 4.4/8.15) for why the source is
genuinely ambiguous in each case."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def test_same_name_in_another_scope_cannot_replace_specs():
    import tempfile
    from types import SimpleNamespace
    import lift_resolve as lr

    text = 'ensures false'
    parser = lr._Parser(lr._lex(text, 0, lr._compute_line_starts(text)), text)
    original_specs = tuple(parser._parse_mspec_list())
    method = SimpleNamespace(name='M', line=2, specs=original_specs, body=())
    source = 'class C { method M() ensures true {} }\nmethod M() ensures false {}\n'
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'input.dfy'
        path.write_text(source, encoding='utf-8')
        warnings, refusal = lr.check_against_source(path, method)
    assert refusal is not None or lr._struct_eq(method.specs, original_specs)


def test_ghost_loop_cannot_bypass_invariant_correction():
    import tempfile
    from types import SimpleNamespace
    import lift_resolve as lr
    from lift_ast import AssertByStmt

    def clauses(text, loop=False):
        parser = lr._Parser(lr._lex(text, 0, lr._compute_line_starts(text)), text)
        return tuple(parser._parse_loopspec_list() if loop else parser._parse_mspec_list())

    expected = clauses('invariant (n / 100) * (n / 100) == 5', loop=True)
    loop = object.__new__(lr.WhileStmt)
    object.__setattr__(loop, 'body', ())
    object.__setattr__(loop, 'line', 3)
    object.__setattr__(loop, 'specs', clauses('invariant n / 100 * n / 100 == 5', loop=True))
    # The walker ignores AssertByStmt without inspecting any of its fields.
    ghost = object.__new__(AssertByStmt)
    method = SimpleNamespace(name='M', line=1,
                             specs=clauses('requires n == 299'),
                             body=(loop, ghost))
    source = '''method M(n: int) requires n == 299 {
      while false invariant (n / 100) * (n / 100) == 5 {}
      assert true by { while false {} }
    }'''
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'input.dfy'
        path.write_text(source, encoding='utf-8')
        warnings, refusal = lr.check_against_source(path, method)
    assert refusal is not None or lr._struct_eq(loop.specs, expected)
