import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Five findings of the review on let expansion: an unread right-hand side with an obligation is not substituted away; a typed binder's subset obligation is kept; a receiver-qualified method call is impure; a such-that let's predicate is in the binder's scope; the method-name iterable is materialised once.


def test_unused_rhs_must_not_erase_division_obligation():
    import lift_let
    from test_lift_let import expr
    out = lift_let.expand(expr('var unused := 1 / 0; true'))
    assert out.issues, 'Silently erased an unavoidable division-by-zero obligation'


def test_nat_binder_constraint_must_not_disappear():
    import lift_let
    from test_lift_let import expr
    out = lift_let.expand(expr('var k: nat := -1; k == -1'))
    assert out.issues, 'Silently erased the impossible nat membership obligation'


def test_receiver_qualified_method_rhs_is_refused():
    import lift_let
    from test_lift_let import expr
    out = lift_let.expand(
        expr('var h := o.Helper(a); h'), method_names=('Helper',))
    assert 'let-impure-rhs' in [issue[1] for issue in out.issues]


def test_such_that_predicate_is_in_binder_scope():
    import lift_let
    from test_lift_let import expr, same
    original = expr('var k: int :| k > a; k')
    result = lift_let.substitute(original, {'k': expr('0')})
    assert same(result, original)


def test_method_name_iterator_applies_to_closure():
    import lift_let
    import lift_parse as lp
    module = lp.parse(
        'function F(a: int): int\n{\n  var h := Helper(a); h\n}\n\n'
        'method M(a: int) returns (r: int)\n{\n  r := a;\n}\n')
    method = next(d for d in module.decls if getattr(d, 'name', None) == 'M')   # M has no ensures: not gradable, still a scope
    function = next(d for d in module.decls if d.name == 'F')
    out = lift_let.expand_scope(
        method, (function,), method_names=iter(['Helper']))
    assert [issue[1] for issue in out.issues] == ['let-impure-rhs']
