import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Two findings of the review on tlib's explanations: a missing kernel is not explained as a missing twin, and a named lowering refusal keeps its name.


def test_explain_kernel_absence_does_not_claim_no_twin():
    import tlib
    entry = {'real': None, 'twin': None,
             'refused': 'kernel absent: dafny not found'}
    sentence = tlib.explain(entry)
    assert 'kernel absent: dafny not found' in sentence
    assert 'no twin' not in sentence


def test_explain_preserves_named_lowering_refusal():
    import tlib
    entry = {'real': 'abstain', 'twin': 'abstain',
             'twin_op': 'collapse-if', 'provisional': False,
             'refused': 'abstain: unsupported construct: forall'}
    sentence = tlib.explain(entry)
    assert 'unsupported construct: forall' in sentence
