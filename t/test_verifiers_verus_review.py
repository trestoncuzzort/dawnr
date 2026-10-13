import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Six findings of the GPT-6 Astra review of 2026-10-13 on the Verus adapter, each reproduced before its fix.


def test_unknown_is_not_a_satisfiability_certificate():
    import json
    from types import SimpleNamespace
    from unittest.mock import patch
    from verifiers import verus as v

    source = '''use vstd::prelude::*;
verus! {
proof fn bad(x: int, y: int, z: int)
    requires x * (y + z) != x * y + x * z,
    ensures false,
{
    assert(x * (y + z) == x * y + x * z) by (nonlinear_arith);
}
}
fn main() {}
'''
    targets = [f for f in v._fns(source) if 'requires' in f['clauses']]
    _, lines = v._build_probe(source, targets)
    stderr = ''.join(
        f'error: assertion failed\n  --> probe.rs:{line}:5\n'
        for line in lines
    )
    reply = SimpleNamespace(
        stdout=json.dumps({'verification-results': {
            'verified': 1, 'errors': 2, 'success': False}}),
        stderr=stderr, returncode=1)
    with patch.object(v, 'run_tree', return_value=reply):
        status, detail = v._probe_vacuity(source, 10)
    assert status != 'clean', detail


def test_user_canary_suffix_cannot_hide_vacuity():
    import json
    from types import SimpleNamespace
    from unittest.mock import patch
    from verifiers import verus as v

    source = '''use vstd::prelude::*;
verus! {
proof fn ok_canary(x: int) requires x >= 0, ensures true {}
proof fn bad_canary(x: int) requires x < x, ensures false {}
}
fn main() {}
'''
    targets = [f for f in v._fns(source) if 'requires' in f['clauses']]
    _, lines = v._build_probe(source, targets)
    stderr = ''.join(
        f'error: assertion failed\n  --> probe.rs:{line}:5\n'
        for line, name in lines.items() if name != 'bad_canary'
    )
    reply = SimpleNamespace(
        stdout=json.dumps({'verification-results': {
            'verified': 3, 'errors': 2, 'success': False}}),
        stderr=stderr, returncode=1)
    with patch.object(v, 'run_tree', return_value=reply):
        status, detail = v._probe_vacuity(source, 10)
    assert status != 'clean', detail


def test_quote_character_cannot_hide_a_vacuous_function():
    import json
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch
    from verifiers import verus as v

    source = '''use vstd::prelude::*;
verus! {
proof fn honest() ensures true {}
fn quote() -> char { '"' }
proof fn bad(x: int) requires x < x, ensures false {}
}
fn main() {}
'''
    reply = SimpleNamespace(
        stdout=json.dumps({'verification-results': {
            'verified': 3, 'errors': 0, 'success': True}}),
        stderr='', returncode=0)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'input.rs'
        path.write_text(source, encoding='utf-8')
        with patch.object(v, 'run_tree', return_value=reply), patch.object(v, 'version', return_value='test'):
            result = v.verify(path)
    assert not result.ok


def test_raw_identifier_cannot_bypass_vacuity():
    import json
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch
    from verifiers import verus as v

    source = '''use vstd::prelude::*;
verus! {
proof fn honest() ensures true {}
proof fn r#bad(x: int) requires x < x, ensures false {}
}
fn main() {}
'''
    reply = SimpleNamespace(
        stdout=json.dumps({'verification-results': {
            'verified': 2, 'errors': 0, 'success': True}}),
        stderr='', returncode=0)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'input.rs'
        path.write_text(source, encoding='utf-8')
        with patch.object(v, 'run_tree', return_value=reply), patch.object(v, 'version', return_value='test'):
            result = v.verify(path)
    assert not result.ok


def test_raw_byte_string_cannot_fabricate_theorem_evidence():
    import json
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch
    from verifiers import verus as v

    source = '''use vstd::prelude::*;
verus! {
fn id(x: u64) -> u64 { x }
}
fn main() {
    let _ = br#"" proof fn ghost() ensures true {} "#;
}
'''
    reply = SimpleNamespace(
        stdout=json.dumps({'verification-results': {
            'verified': 1, 'errors': 0, 'success': True}}),
        stderr='', returncode=0)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'input.rs'
        path.write_text(source, encoding='utf-8')
        with patch.object(v, 'run_tree', return_value=reply), patch.object(v, 'version', return_value='test'):
            result = v.verify(path)
    assert not result.ok


def test_block_precondition_is_not_the_function_body():
    from verifiers import verus as v

    source = 'verus! { proof fn p() requires { let b = true; b }, ensures true {} }'
    function = next(f for f in v._fns(source) if f['name'] == 'p')
    requires = function['clauses']['requires'].strip().rstrip(',').strip()
    assert requires == '{ let b = true; b }', function
    assert 'ensures' in function['clauses'], function
