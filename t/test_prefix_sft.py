"""prefix_sft: the shared-prefix schedule gives the plain per-row loss and gradients, exactly, on a tiny random model."""
import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

needs = [m for m in ("torch", "transformers") if importlib.util.find_spec(m) is None]
pytestmark = pytest.mark.skipif(bool(needs), reason=f"needs {', '.join(needs)}")


def _has_qwen35():
    try:
        from transformers import Qwen3_5TextConfig  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _has_qwen35(), reason="this transformers has no Qwen3.5")
def test_shared_prefix_is_exact_in_64_bit():
    import prefix_sft
    out = prefix_sft.check(seed=2, batch=4, prefix=70, verbose=False, layers="LLFL", exact64=True)
    for key in ("shared", "shared_ckpt"):
        assert out[key]["loss_diff"] < 1e-8, out
        assert out[key]["worst_grad_rel"] < 1e-6, out
        assert not out[key]["missing"], out


def test_common_prefix_and_split():
    import prefix_sft
    rows = [{"input_ids": [5, 6, 7, 8, 9], "labels": [-100, -100, -100, 8, 9]},
            {"input_ids": [5, 6, 7, 1, 2, 3], "labels": [-100, -100, -100, -100, 2, 3]}]
    assert prefix_sft.common_prefix([r["input_ids"] for r in rows]) == 3
    parts = prefix_sft.split(rows, pad_id=0)
    assert parts["prefix_ids"].tolist() == [[5, 6, 7]]
    assert parts["suffix_ids"].tolist() == [[8, 9, 0], [1, 2, 3]]
    assert parts["suffix_labels"].tolist() == [[8, 9, -100], [-100, 2, 3]]
    assert parts["suffix_mask"].tolist() == [[1, 1, 0], [1, 1, 1]]
