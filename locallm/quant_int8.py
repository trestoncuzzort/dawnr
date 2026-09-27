"""quant_int8.py — weight-only int8 for the torch sampling path. Off by default.

    from quant_int8 import quantize_model_int8
    model, tok, cfg = checkpoint.load_checkpoint(out_dir)
    report = quantize_model_int8(model)     # in place; nothing calls this on its own
    text = checkpoint.sample(model, tok, "...", temperature=0)

Nothing in model.py or checkpoint.py imports this module or calls it: a caller
opts in explicitly, after loading a float checkpoint the usual way, which is
what "off by default" means here — the shipped checkpoint, the app and every
existing test keep running in float32 unless this is asked for.

THE SCHEME is plain_generate.py's --quantize, the torch way: per-output-channel
(one scale per output row, i.e. per weight matrix row / per nn.Linear output
feature) symmetric quantization, restricted to the SIMD-friendly range
[-127, 127] with the zero-point fixed at 0 (Krishnamoorthi 2018, arXiv:1806.08342,
section 2.2's uniform symmetric quantizer, eq. 7-10, and section 2.6's per-channel
granularity). It is WEIGHT-ONLY quantization: activations and the hidden state
stay float32 throughout (section 3.1.1, "weight only quantization" — "this can
be done without requiring any validation data... does not mind the cost of
performing inference in floating point"), so QuantizedLinear.forward below
dequantizes the WEIGHT before the matmul rather than quantizing the input.
`torch.quantize_per_channel` (docs.pytorch.org/docs/2.14/generated/
torch.quantize_per_channel.html) takes one scale per index along an axis — the
same per-row convention used here, reimplemented directly on plain torch.int8
tensors rather than torch's qint8 dtype so this has no dependency on which
quantization backend (fbgemm/qnnpack) a given torch build shipped with, and
works the same on CPU, CUDA or MPS.

nn.Embedding (wte, wpe) is left alone here: it is read by index, not matrix-
multiplied, so per-channel-of-a-matmul quantization does not apply to it the
same way, and quantizing it needs a separate scheme this module does not
implement (AMBITION.md's "to fit small hardware: quantisation... partly" row).
plain_generate.py's --quantize, in the standard library, DOES cover wte/wpe,
row by row, the same construction — see its module docstring.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
from torch.nn import functional as F

_QLEVEL = 127.0   # signed 8-bit, restricted range: clamp(-127, 127), not -128


def quantize_tensor_per_channel_symmetric(weight: torch.Tensor):
    """(out, in) float weight -> (int8 (out, in), float32 scale (out,)).

    One scale per output row (dim 0): scale = max(abs(row)) / 127, quantized =
    round(row / scale) clamped to [-127, 127] — plain_generate.py's
    _quantize_row, on a tensor instead of an array('f'). A row that is exactly
    zero gets scale 1.0 (its own quantized row is already all zero, so any
    positive scale dequantizes it back to zero) rather than dividing by zero.
    """
    if weight.dim() != 2:
        raise ValueError(f"expected a 2-D (out, in) weight, got shape {tuple(weight.shape)}")
    with torch.no_grad():
        peak = weight.detach().abs().amax(dim=1)
        scale = torch.where(peak > 0, peak / _QLEVEL, torch.ones_like(peak))
        quantized = (weight.detach() / scale.unsqueeze(1)).round().clamp(-_QLEVEL, _QLEVEL)
        return quantized.to(torch.int8), scale.to(torch.float32)


def dequantize_per_channel_symmetric(quantized: torch.Tensor, scale: torch.Tensor) -> torch.Tensor:
    """The inverse of the function above, for tests and for a caller that wants
    the plain float weight back (e.g. to diff it against the original)."""
    return quantized.to(scale.dtype) * scale.unsqueeze(1)


class QuantizedLinear(nn.Module):
    """A drop-in for nn.Linear whose weight is int8 plus one scale per output row.

    forward dequantizes the WEIGHT (int8 * scale, both cast to the input's
    dtype) and calls the ordinary F.linear — bias and the input stay whatever
    dtype they arrived in, so this is weight-only quantization, not full
    integer inference. Kept as its own module, built from an existing
    nn.Linear's weight, rather than mutating nn.Linear.weight in place, so a
    float model and a quantized copy of it can be compared side by side without
    either module fighting the other over what dtype its own weight is.
    """

    def __init__(self, weight_int8: torch.Tensor, scale: torch.Tensor, bias):
        super().__init__()
        if weight_int8.dtype != torch.int8:
            raise ValueError(f"weight_int8 must be torch.int8, got {weight_int8.dtype}")
        if scale.shape != weight_int8.shape[:1]:
            raise ValueError("scale must have one entry per output row")
        self.in_features = weight_int8.shape[1]
        self.out_features = weight_int8.shape[0]
        self.register_buffer("weight_int8", weight_int8)
        self.register_buffer("scale", scale)
        self.bias = None if bias is None else nn.Parameter(bias.detach().clone())

    @classmethod
    def from_linear(cls, linear: nn.Linear) -> "QuantizedLinear":
        weight_int8, scale = quantize_tensor_per_channel_symmetric(linear.weight)
        return cls(weight_int8, scale, linear.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        weight = self.weight_int8.to(x.dtype) * self.scale.to(x.dtype).unsqueeze(1)
        return F.linear(x, weight, self.bias)

    def weight_bytes(self) -> int:
        """int8 rows plus their float32 scales — never the (unquantized) bias."""
        return (self.weight_int8.numel() * self.weight_int8.element_size()
               + self.scale.numel() * self.scale.element_size())

    def extra_repr(self) -> str:
        return (f"in_features={self.in_features}, out_features={self.out_features}, "
               f"bias={self.bias is not None}, dtype=int8")


@dataclass
class QuantizeReport:
    """What quantize_model_int8 changed, for a caller to print or assert on."""
    modules_quantized: int
    float_bytes: int
    int8_bytes: int

    @property
    def ratio(self) -> float:
        """int8_bytes / float_bytes over just the modules this call touched —
        0.0 if it touched none, so a caller can print it without a ZeroDivisionError."""
        return self.int8_bytes / self.float_bytes if self.float_bytes else 0.0


def _replace_linears(module: nn.Module, module_types: tuple, stats: dict) -> None:
    for child_name, child in list(module.named_children()):
        if isinstance(child, module_types) and not isinstance(child, QuantizedLinear):
            replacement = QuantizedLinear.from_linear(child)
            stats["float_bytes"] += child.weight.numel() * child.weight.element_size()
            stats["int8_bytes"] += replacement.weight_bytes()
            stats["count"] += 1
            setattr(module, child_name, replacement)
        else:
            _replace_linears(child, module_types, stats)


def quantize_model_int8(model: nn.Module, *, module_types=(nn.Linear,)) -> QuantizeReport:
    """Replace every matching submodule's weight with an int8 QuantizedLinear, in place.

    Off by default in the sense that matters: this function exists in its own
    module and nothing elsewhere calls it, so loading and sampling a checkpoint
    the ordinary way (checkpoint.load_checkpoint, model.generate) never touches
    it. A caller quantizes by calling this once, explicitly, after loading.

    Recurses into every submodule so it reaches attn.c_attn, attn.c_proj,
    mlp.c_fc/c_proj (or gate_up/c_proj for the `modern` core's SwiGLU) and
    lm_head in every transformer block, without hardcoding GPT's own attribute
    names — a future architecture in model.py needs no change here.
    """
    stats = {"count": 0, "float_bytes": 0, "int8_bytes": 0}
    _replace_linears(model, module_types, stats)
    return QuantizeReport(stats["count"], stats["float_bytes"], stats["int8_bytes"])


def linear_weight_bytes(model: nn.Module) -> int:
    """Bytes held right now by every nn.Linear or QuantizedLinear weight in this
    model (bias excluded either way) — independent of any one
    quantize_model_int8 call's own report, so a test can check the model itself
    rather than trust what the report says about it."""
    total = 0
    for module in model.modules():
        if isinstance(module, QuantizedLinear):
            total += module.weight_bytes()
        elif isinstance(module, nn.Linear):
            total += module.weight.numel() * module.weight.element_size()
    return total
