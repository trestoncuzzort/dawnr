# train 1: PyTorch 2.13.0+cpu, the exact wheels hashed at fetch, offline.
cd /sources/wheels
sha256sum -c SHA256SUMS-at-fetch
pip install --no-index --find-links=/sources/wheels torch==2.13.0+cpu
python3 - <<'PY'
import torch
x = torch.randn(64, 64, requires_grad=True)
loss = (x @ x).sum()
loss.backward()
assert x.grad is not None and x.grad.shape == (64, 64)
print(f"torch {torch.__version__}: gradient computed on {x.device}")
PY
