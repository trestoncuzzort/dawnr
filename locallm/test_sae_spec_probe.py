"""sae_spec_probe.py's pieces that need no model: the split, the spans, AUROC, and the TopK SAE arithmetic
(Qwen-Scope's: pre = x W_enc^T + b_enc, keep the top k, x_hat = a W_dec^T + b_dec)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sae_spec_probe as p  # noqa: E402


def test_the_split_is_by_problem_and_fixed():
    assert p.split_of(113) == p.split_of(113)
    sides = {p.split_of(i) for i in range(60)}
    assert sides == {"choose", "test"}
    assert 0.2 < sum(p.split_of(i) == "test" for i in range(3000)) / 3000 < 0.45


def test_ensures_spans_cover_exactly_the_ensures_lines():
    text = "t 1\ntask f(n: int) returns (r: int)\n  ensures r == n\n  ensures r >= 0\n{\n  r := n;\n}\n"
    spans = p.ensures_spans(text)
    assert [text[s:e] for s, e in spans] == ["  ensures r == n", "  ensures r >= 0"]


def test_auroc_with_ties():
    assert p.auroc([0.9, 0.1], [True, False]) == 1.0
    assert p.auroc([0.5, 0.5], [True, False]) == 0.5
    assert p.auroc([0.1, 0.9, 0.5], [True, False, True]) == 0.0
    assert p.auroc([0.5, 0.5, 0.9], [True, False, False]) == 0.25


def test_topk_sae_keeps_k_features_and_decodes(tmp_path):
    import torch
    torch.manual_seed(0)
    d = {"W_enc": torch.randn(16, 4), "b_enc": torch.zeros(16), "W_dec": torch.randn(4, 16), "b_dec": torch.zeros(4)}
    torch.save(d, tmp_path / "s.pt")
    sae = p.TopKSAE(tmp_path / "s.pt", k=3)
    x = torch.randn(5, 4)
    acts = sae.encode(x)
    assert ((acts != 0).sum(-1) <= 3).all()
    assert sae.decode(acts).shape == (5, 4)
