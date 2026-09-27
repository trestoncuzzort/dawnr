"""plain_generate.py — read a ckpt.pt and write text with NOTHING installed.

    python3 plain_generate.py --out mymodel --prompt "function to find the "

No torch, no numpy, no wheels, no compiler: zipfile, pickle, array, math and
random, all of which ship with Python itself. The point is a USB stick that
works on a computer where `pip install torch` is 196 MB of the wrong platform's
binary, or is not allowed at all. `SHIPPING.md` has the sizes and the honest
split between what this covers and what still needs torch.

WHY THIS IS POSSIBLE AT ALL. These models are small enough that the arithmetic
is not the problem. A decode step with a key/value cache costs about one
multiply-accumulate per parameter, so the 10.9M-parameter round-4 checkpoint
costs ~13.0M multiply-accumulates per token at full context. Plain CPython does
~48M of them per second through `sum(map(mul, row, x))` over `array('f')` rows,
and about twice that through math.sumprod on Python 3.12+ (see _dot below):
102-117 ms per token on that checkpoint and 47-56 ms on the 4.9M one, measured
2026-09-26 (SHIPPING.md, section 2). That is slow and it is not nothing: a
200-token answer in 24 seconds, from a stick, on a computer with no
machine-learning software on it.

WHERE THE FORMAT CAME FROM. Not guesswork.
docs.pytorch.org/docs/2.14/notes/serialization.html: since PyTorch 1.6.0
`torch.save` writes an uncompressed ZIP64 archive of `data.pkl`, `byteorder`,
`data/0`, `data/1`, ... and `version`, where `data.pkl` is the pickle of the
saved object EXCLUDING its storages and each storage is one member of `data/`
holding raw element bytes. So the pickle gives shapes and the zip members give
numbers, and neither step needs torch. pytorch/pytorch#45394 is someone asking
for exactly this in 2020 ("Due to prerequisites limitations, I am not able to
install torch") and the thread closed with no answer.

The forward pass follows tairov/llama2.py, which runs a whole transformer in one
file of pure Python and publishes 1.3 tok/s on 15M parameters in native CPython
on an M1 Max. Ours is faster for two reasons that are ours and not theirs: 10.9M
parameters rather than 15M, and a character vocabulary of 82 entries rather than
32,000, which makes the output projection 31,488 multiply-accumulates per token
instead of about 9.2M. jaymody/picoGPT does the same job in ~40 lines of NumPy
and was rejected only because NumPy is the wheel we are trying not to need.

WHAT THIS DELIBERATELY DOES NOT DO.

  * No training. Backward passes need an optimizer, mixed precision and hours of
    arithmetic; at 48M MAC/s that is not a thing anyone should wait for. Training
    is torch's job and `SHIPPING.md` says so.
  * Only `architecture="gpt"`. Every checkpoint in this repository is that, and
    it is what `studio.py` builds (it never passes `architecture`, so it gets
    `GPTConfig`'s default) and what `train.py` defaults to without `--preset`.
    The `modern` core needs RMSNorm, rotary positions and SwiGLU, which is about
    25 more lines — and there is no `modern` checkpoint here to check them
    against, so this refuses that config by name rather than guess at it.
  * Only character tokenizers, the plain JSON list `CharTokenizer.save` writes.
    A byte-BPE `tokenizer.json` needs the `tokenizers` package to decode, which
    is a wheel again; this refuses it by name.
  * Sampling is not torch's sampler. `random.choices` draws from the same
    distribution as `torch.multinomial` but not from the same stream, so a seed
    here and a seed there give different text. Greedy decoding
    (`temperature=0`) is the comparable one, and even that can differ in the
    last place because float32 sums accumulate in a different order.

WEIGHTS CAN BE HELD AS INT8 INSTEAD OF FLOAT32, off by default. `--quantize`
stores every weight row as one array('b') plus one float32 scale rather than an
array('f') (about a quarter the bytes); `--quantize-kv` does the same to the
key/value cache this file already keeps in Python lists. Both are the symmetric,
per-row scheme in Krishnamoorthi 2018 (arXiv:1806.08342) sections 2.2 and 2.6 —
see `_quantize_row` below for the exact arithmetic. Neither is claimed free:
`bench_int8.py` measures speed, memory and greedy-output agreement against
float32 on the included model rather than assuming either
(`bench-int8-results-2026-09-27.json` has the numbers), so both stay opt-in.

The API mirrors `checkpoint.py` on purpose — `checkpoint_exists`,
`load_checkpoint`, `sample` with the same arguments — so a caller switches
between the torch path and this one by changing which module it imports, and
neither file had to learn about the other.
"""
from __future__ import annotations

import argparse
import array
import io
import json
import math
import pickle
import random
import sys
import zipfile
from operator import mul
from pathlib import Path

# array type code and element width per torch storage class. bfloat16 is absent
# on purpose: `array` has no such code, the conversion is a 16-bit shift into the
# high half of a float32, and no checkpoint here is saved that way, so it would
# ship untested. It raises below, named.
_STORAGE = {"FloatStorage": ("f", 4), "DoubleStorage": ("d", 8), "HalfStorage": ("e", 2)}

# Everything the checkpoint pickle is allowed to name. Unpickling runs arbitrary
# code by construction (docs.python.org/3/library/pickle.html: "It is possible to
# construct malicious pickle data which will execute arbitrary code during
# unpickling"), and a stranger's stick may hold a checkpoint a stranger sent
# them. torch.load grew `weights_only=True` for this reason; the equivalent here
# is that find_class resolves only these names and raises on every other.
_ALLOWED = {
    ("collections", "OrderedDict"),
    ("torch._utils", "_rebuild_tensor"),
    ("torch._utils", "_rebuild_tensor_v2"),
}


class _Refused(Exception):
    """A checkpoint this module will not read, with the reason in the message."""


# The name a caller catches: the message is a sentence meant to be shown as it is
# (home.py puts it on a card), so a caller should not have to reach for a
# private name to tell it from a crash.
Refused = _Refused


class _Loader(pickle.Unpickler):
    """Rebuild tensor metadata; fetch element bytes from the zip on demand.

    Storages are cached by key because tied weights share one: `wte.weight` and
    `lm_head.weight` are the same storage in every checkpoint here, which is also
    why a 10,875,648-parameter model is 43,526,601 bytes on disk and not twice
    that.
    """

    def __init__(self, data_pkl: bytes, archive: zipfile.ZipFile, prefix: str):
        super().__init__(io.BytesIO(data_pkl))
        self._zip, self._prefix, self._cache = archive, prefix, {}

    def find_class(self, module, name):
        if (module, name) in _ALLOWED:
            if module == "collections":
                import collections
                return collections.OrderedDict
            return self._rebuild
        if module.startswith("torch") and name.endswith("Storage"):
            # persistent_load reads the width off this; a lambda would arrive
            # there anonymous and the dtype would be unrecoverable.
            return type(name, (), {"__module__": module, "__qualname__": name})
        raise _Refused(
            f"this checkpoint's pickle names {module}.{name}, which a weights-only "
            f"reader will not resolve. Load it with torch instead, or re-save it "
            f"as a plain state_dict.")

    def persistent_load(self, pid):
        # ("storage", storage_class, key, location, numel). `location` says which
        # device it was saved from and is ignored: raw bytes are raw bytes, so a
        # checkpoint written from "cuda:0" reads here with nothing to map.
        _, storage_class, key, _location, numel = pid
        return (getattr(storage_class, "__qualname__", str(storage_class)), str(key), numel)

    def _storage(self, tag):
        name, key, numel = tag
        if key in self._cache:
            return self._cache[key]
        spec = _STORAGE.get(name)
        if spec is None:
            raise _Refused(
                f"this checkpoint stores weights as {name}, which this reader does "
                f"not convert. Load it with torch, or re-save it in float32.")
        code, width = spec
        values = array.array(code)
        values.frombytes(self._zip.read(f"{self._prefix}/data/{key}")[: numel * width])
        if sys.byteorder != "little":
            values.byteswap()          # the archive is little-endian; see load()
        if code != "f":
            values = array.array("f", values)   # one dtype downstream, not three
        self._cache[key] = values
        return values

    def _rebuild(self, tag, offset, size, stride, *_rest):
        expected = 1
        for dim in size:
            expected *= dim
        contiguous = []
        step = 1
        for dim in reversed(size):
            contiguous.append(step)
            step *= dim
        if tuple(stride) != tuple(reversed(contiguous)):
            # A transposed or otherwise strided view would need index arithmetic
            # this module does not do. Nothing torch.save writes from a state_dict
            # of ordinary parameters is strided, so this is a guard, not a case.
            raise _Refused(f"tensor of shape {tuple(size)} is a strided view; "
                           f"re-save it with .contiguous()")
        return {"shape": tuple(size), "flat": self._storage(tag), "offset": offset,
                "numel": expected}


_LFS_POINTER = b"version https://git-lfs.github.com/spec/v1"


def _read(path: Path):
    """Return (config dict, state dict of tensor descriptions) from a ckpt.pt."""
    with open(path, "rb") as probe:
        head = probe.read(len(_LFS_POINTER))
    if head == _LFS_POINTER:
        # .gitattributes puts *.pt through Git LFS, so a clone made without
        # git-lfs installed leaves a 133-byte text stub here that records the real
        # size and none of the bytes. zipfile's "File is not a zip file" gives a
        # reader no way to guess that, and this is the likeliest way a stranger's
        # copy arrives broken.
        raise _Refused(
            f"{path} is a Git LFS pointer, not the weights: this clone was made "
            f"without git-lfs, so only a {path.stat().st_size}-byte stub was "
            f"checked out. Install git-lfs and run `git lfs pull`, or copy the "
            f"file from a checkout that has it.")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        try:
            data_pkl = next(n for n in names if n.endswith("data.pkl"))
        except StopIteration:
            raise _Refused(f"{path} is a zip but has no data.pkl, so it is not a "
                           f"torch.save archive") from None
        prefix = data_pkl[: -len("/data.pkl")]
        marker = f"{prefix}/byteorder"
        if marker in names and archive.read(marker) != b"little":
            # Present since torch 2.1.0. A big-endian checkpoint would need every
            # storage byteswapped the other way; no machine here writes one.
            raise _Refused(f"{path} was saved on a big-endian machine")
        payload = _Loader(archive.read(data_pkl), archive, prefix).load()
    if not isinstance(payload, dict) or "model" not in payload or "config" not in payload:
        raise _Refused(f"{path} is not a locallm checkpoint: expected a dict with "
                       f"'model' and 'config' keys")
    return payload["config"], payload["model"]


class CharTokens:
    """The character tokenizer, re-read from its own JSON with no import of data.py.

    data.py is not importable without torch (it is imported by everything that is),
    and the file it writes is a plain list of characters, so this is the same
    encode and decode over the same list. Kept to CharTokenizer's interface.
    """

    def __init__(self, chars, sentinels=()):
        self.chars = list(chars)
        # Sentinel ids (fill-in-the-middle; see data.CharTokenizer) follow the
        # characters and are never produced by encode(); decode names them.
        self.sentinels = tuple(sentinels)
        self._index = {c: i for i, c in enumerate(self.chars)}

    @property
    def vocab_size(self) -> int:
        return len(self.chars) + len(self.sentinels)

    def encode(self, text: str):
        # Drops what this model never saw, exactly as data.CharTokenizer.encode
        # does, and for the same reason: the two must agree token for token or a
        # checkpoint reads differently depending on which path opened it.
        # unknown_characters() below is how a caller learns what went missing.
        return [self._index[c] for c in text if c in self._index]

    def unknown_characters(self, text: str) -> dict[str, int]:
        """The characters encode() drops, first appearance first, with counts.

        Character for character what data.CharTokenizer.unknown_characters
        returns; that file carries the reasoning for why this is a separate
        query rather than an errors= flag on encode
        (docs.python.org/3/library/codecs.html). Duplicated rather than imported
        because data.py imports torch at module scope and this module's whole
        claim is that it needs none, which is also why test_tokenizer_drops.py
        pins the two implementations to each other instead of trusting them.
        """
        unknown: dict[str, int] = {}
        for c in text:
            if c not in self._index:
                unknown[c] = unknown.get(c, 0) + 1
        return unknown

    def decode(self, ids) -> str:
        n = len(self.chars)
        return "".join(self.chars[int(i)] if int(i) < n else self.sentinels[int(i) - n] for i in ids)

    @classmethod
    def load(cls, path):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("format") == "locallm-char-tokenizer" \
                and payload.get("version") == 1:
            return cls(payload["chars"], payload.get("sentinels", ()))
        if not (isinstance(payload, list) and all(isinstance(c, str) for c in payload)):
            raise _Refused(
                f"{path} is a byte-BPE tokenizer, which needs the `tokenizers` "
                f"package to decode. This module reads character tokenizers only.")
        return cls(payload)


def _rows(tensor):
    """Split an (out, in) weight into `out` flat float arrays, once, at load.

    Slicing an array.array copies, so doing this per row per token would dominate
    the runtime. Done here it costs the same bytes again for the slices' headers
    and buys an inner loop that is one `sum(map(mul, row, x))` with no slicing.
    """
    out, width = tensor["shape"]
    flat, offset = tensor["flat"], tensor["offset"]
    return [flat[offset + i * width: offset + (i + 1) * width] for i in range(out)]


def _vector(tensor):
    return tensor["flat"][tensor["offset"]: tensor["offset"] + tensor["numel"]]


def _dot_plain(p, q):
    """The dot product every Python has: one Python float per product, summed."""
    return sum(map(mul, p, q))


def _attend_plain(weights, columns):
    """softmax(scores) @ V for one head, in the arithmetic this file always had.

    `weights` are the unnormalised exp(score - max) over time and `columns` are
    the head's values stored one column per dimension, so each output dimension
    is one dot product over time. Normalising the weights first and summing the
    products in time order is, operation for operation, the double loop this
    replaced (`weight *= norm; accumulated[j] += weight * value[j]`); on Python
    3.10 and 3.11, where this is the path taken, `sum` adds floats left to right
    as that loop did, so the result is the same to the last bit.
    """
    norm = 1.0 / sum(weights)
    scaled = [weight * norm for weight in weights]
    return [sum(map(mul, scaled, column)) for column in columns]


def _attend_sumprod(weights, columns):
    """The same product through math.sumprod, normalised once per output."""
    sumprod = math.sumprod
    norm = 1.0 / sum(weights)
    return [sumprod(weights, column) * norm for column in columns]


# THE DOT PRODUCT IS NEARLY ALL OF THE TIME, and Python 3.12 added a better one.
# math.sumprod(p, q) is "roughly equivalent to sum(map(operator.mul, p, q,
# strict=True))" (docs.python.org/3/library/math.html#math.sumprod), but in
# CPython it is one C loop that builds no Python float per product:
# Modules/mathmodule.c, math_sumprod_impl, accumulates float pairs with tl_fma,
# the Ogita-Rump-Oishi accurate dot product (doi.org/10.1137/030601818), and
# rounds once at the end. So it is about twice as fast as the sum, and slightly
# MORE accurate, which also means its last bit can differ from the sum's and a
# greedy choice between two near-equal logits could in principle flip. That was
# checked over 200 greedy tokens on the included model against the old code
# (SHIPPING.md, section 2). Python 3.10 and 3.11 have no sumprod and keep the
# old arithmetic exactly. The values are stored one column per head dimension
# (see PlainGPT.reset) so that attention is dot products too: the old double
# loop over (time, dimension) in Python was the one place no C loop helped.
if hasattr(math, "sumprod"):
    _dot, _attend = math.sumprod, _attend_sumprod
else:
    _dot, _attend = _dot_plain, _attend_plain


# --- int8 KV-cache: the same symmetric per-row quantizer (_quantize_row above),
# applied to one cached key or value VECTOR at a time instead of one weight row.
# Krishnamoorthi 2018 states the quantizer (its section 2) generically over "a
# floating point variable" and generalizes granularity to per-channel (2.6)
# without restricting either to weight tensors, so no separate source is cited
# for this: it is the same construction at a different granularity, argued in
# the same commit that adds it.
#
# Keys: scale is one float per cached vector, so scores = dot(q, k_int8) *
# key_scale * attn_scale — the same "multiply once, after the sum" factoring as
# _matvec_int8, just with an extra per-key scalar.
#
# Values: harder, because _attend sums OVER TIME for one output dimension at a
# time (columns[j] is dimension j's value across every cached position), and
# here EVERY position has its OWN scale (unlike a weight row, where one scale
# covered the whole row). But scale is still a plain number, so
#     sum_t weight[t] * value[t][j]
#   = sum_t weight[t] * (value_scale[t] * int8_value[t][j])
#   = sum_t (weight[t] * value_scale[t]) * int8_value[t][j]
# which is _attend's own dot product over column j, with the softmax weights
# pre-multiplied by each position's value_scale ONCE (O(T), not O(T * head_dim))
# before the per-dimension loop, so the per-dimension inner loop below still
# runs over a raw int8 column with no per-element dequantizing.
def _attend_int8_plain(weights, columns, value_scales):
    # Folds norm into the same pre-multiply as value_scale, matching
    # _attend_plain's own choice to scale the weights once before summing
    # rather than scale the sum once after.
    norm = 1.0 / sum(weights)
    adjusted = [w * s * norm for w, s in zip(weights, value_scales)]
    return [sum(map(mul, adjusted, column)) for column in columns]


def _attend_int8_sumprod(weights, columns, value_scales):
    sumprod = math.sumprod
    norm = 1.0 / sum(weights)
    adjusted = [w * s for w, s in zip(weights, value_scales)]
    return [sumprod(adjusted, column) * norm for column in columns]


if hasattr(math, "sumprod"):
    _attend_int8 = _attend_int8_sumprod
else:
    _attend_int8 = _attend_int8_plain


def _matvec(rows, x, bias):
    dot = _dot
    return [dot(row, x) + b for row, b in zip(rows, bias)]


# --- int8 weight quantization: per-row (per-channel), symmetric, OFF BY DEFAULT ---
#
# Krishnamoorthi 2018 (arXiv:1806.08342), section 2.2's uniform SYMMETRIC
# quantizer restricted to the SIMD-friendly range (eq. 7-10: zero-point fixed at
# 0, clamp to [-(N/2-1), N/2-1] = [-127, 127] for signed 8-bit) and section 2.6's
# PER-CHANNEL granularity (one scale per output row, rather than one for the
# whole tensor). Section 3.1.1, "weight only quantization", is this file's case
# exactly: only the weights shrink to int8, activations (the hidden state `x`
# below) stay float32, and "one does not mind the cost of performing inference
# in floating point" — table 2 there also shows this is not free: symmetric
# per-channel weight-only quantization lands close to floating-point accuracy
# but not always at it (0.591-0.78 against 0.708-0.78 float, across their CNNs),
# which is why this file's own tests measure greedy-output agreement rather
# than assume it. `torch.quantize_per_channel`
# (docs.pytorch.org/docs/2.14/generated/torch.quantize_per_channel.html) takes
# one scale per index along an axis — the same per-row convention used here.
#
# WHY THE SCALE FACTORS OUT OF THE DOT PRODUCT. scale is one float for the
# WHOLE row, so dequantizing element i is `quantized[i] * scale`, and because
# scalar multiplication distributes over a sum,
#     dot(dequantized_row, x) == dot(quantized_row, x) * scale
# exactly (up to one extra floating-point rounding, not one per element). That
# is why _matvec_int8 below multiplies by `scale` once per output row instead
# of dequantizing a 384-wide row back to float before every dot product: doing
# that would rebuild, at every step, the very float32 row this format exists to
# not keep in memory.
def _quantize_row(row):
    """One float row -> (int8 array, scale). Dequantizing element i is
    `quantized[i] * scale`. An all-zero row gets scale=1.0 (0 * 1.0 == 0), so a
    fresh key/value vector before any signal ever divides by zero."""
    peak = max((abs(v) for v in row), default=0.0)
    scale = peak / 127.0 if peak else 1.0
    inv = 1.0 / scale
    return (array.array("b", (min(127, max(-127, round(v * inv))) for v in row)),
            scale)


def _quantize_rows(rows):
    """[float row, ...] -> ([int8 row, ...], array('f') of one scale per row)."""
    quantized, scales = [], array.array("f")
    for row in rows:
        q, scale = _quantize_row(row)
        quantized.append(q)
        scales.append(scale)
    return quantized, scales


def _load_weight(tensor, quantize: bool):
    """A weight's rows as _rows() always returned them, quantized to int8 first
    if `quantize`. `scales` is None for float32 rows, so every caller below —
    _matvec_int8's dispatch, _embed_row, weight_bytes — has exactly one thing to
    check to know which kind of row it is holding.
    """
    rows = _rows(tensor)
    return _quantize_rows(rows) if quantize else (rows, None)


def _embed_row(rows, scales, index):
    """One row of an embedding table, dequantized if it is int8.

    Returns the row itself (an array('f'), not a copy) when unquantized, so
    `zip(_embed_row(self.wte, None, token), ...)` costs exactly what
    `zip(self.wte[token], ...)` always did.
    """
    if scales is None:
        return rows[index]
    return [v * scales[index] for v in rows[index]]


def _matvec_int8(rows, scales, x, bias):
    """_matvec over int8 rows: dot(int8_row, x) * scale + bias — see above for
    why multiplying by `scale` once per row, after the dot product, is exact."""
    dot = _dot
    return [dot(row, x) * s + b for row, s, b in zip(rows, scales, bias)]


def _layernorm(x, weight, bias, eps=1e-5):
    """nn.LayerNorm's default: biased variance over the last axis, eps 1e-5."""
    n = len(x)
    mean = sum(x) / n
    var = sum((value - mean) ** 2 for value in x) / n
    scale = 1.0 / math.sqrt(var + eps)
    return [(value - mean) * scale * w + b for value, w, b in zip(x, weight, bias)]


_SQRT2 = math.sqrt(2.0)


def _gelu(values):
    """nn.GELU()'s default is the exact erf form, not the tanh approximation."""
    return [0.5 * v * (1.0 + math.erf(v / _SQRT2)) for v in values]


class PlainGPT:
    """One GPT, decoded a token at a time against its own key/value cache.

    Without the cache each step would re-read the whole prefix, which is the
    context length times the work for the same answer. The cache is the
    difference between about 110 ms and tens of seconds per token, so unlike
    model.py's opt-in `use_cache` it is not optional here.
    """

    def __init__(self, config, state, quantize: bool = False, quantize_kv: bool = False):
        if config.get("architecture", "gpt") != "gpt":
            raise _Refused(
                f"this checkpoint is architecture={config['architecture']!r}, which "
                f"needs RMSNorm, rotary positions and SwiGLU. This module reads the "
                f"gpt core only.")
        self.config = dict(config)
        self.n_layer = config["n_layer"]
        self.n_head = config["n_head"]
        self.n_embd = config["n_embd"]
        self.head_dim = self.n_embd // self.n_head
        self.block_size = config["block_size"]
        self.vocab_size = config["vocab_size"]
        # quantize: every 2-D weight (embeddings, qkv/projection/mlp matrices,
        # lm_head) is stored as int8 rows plus one float32 scale per row instead
        # of float32 rows (see _quantize_row and _load_weight above).
        # quantize_kv: the key/value cache this model keeps across step() calls
        # (see reset, step) is stored the same way, one scale per cached vector.
        # Both default False: identical weights, identical arithmetic, identical
        # output to before either flag existed (TheDefaultIsUnquantized in
        # test_plain_generate.py pins this down).
        self.quantize, self.quantize_kv = quantize, quantize_kv
        if "transformer.wpe.weight" not in state:
            raise _Refused("no learned position table; this is not a gpt-core checkpoint")
        self.wte, self.wte_scale = _load_weight(state["transformer.wte.weight"], quantize)
        self.wpe, self.wpe_scale = _load_weight(state["transformer.wpe.weight"], quantize)
        self.layers = []
        for i in range(self.n_layer):
            p = f"transformer.h.{i}."
            qkv_w, qkv_scale = _load_weight(state[p + "attn.c_attn.weight"], quantize)
            attn_out_w, attn_out_scale = _load_weight(state[p + "attn.c_proj.weight"], quantize)
            fc_w, fc_scale = _load_weight(state[p + "mlp.c_fc.weight"], quantize)
            mlp_out_w, mlp_out_scale = _load_weight(state[p + "mlp.c_proj.weight"], quantize)
            self.layers.append({
                "ln1_w": _vector(state[p + "ln_1.weight"]),
                "ln1_b": _vector(state[p + "ln_1.bias"]),
                "ln2_w": _vector(state[p + "ln_2.weight"]),
                "ln2_b": _vector(state[p + "ln_2.bias"]),
                "qkv_w": qkv_w, "qkv_scale": qkv_scale,
                "qkv_b": _vector(state[p + "attn.c_attn.bias"]),
                "attn_out_w": attn_out_w, "attn_out_scale": attn_out_scale,
                "attn_out_b": _vector(state[p + "attn.c_proj.bias"]),
                "fc_w": fc_w, "fc_scale": fc_scale,
                "fc_b": _vector(state[p + "mlp.c_fc.bias"]),
                "mlp_out_w": mlp_out_w, "mlp_out_scale": mlp_out_scale,
                "mlp_out_b": _vector(state[p + "mlp.c_proj.bias"]),
            })
        self.ln_f_w = _vector(state["transformer.ln_f.weight"])
        self.ln_f_b = _vector(state["transformer.ln_f.bias"])
        # Tied to wte in model.py, but a checkpoint records both names, so read
        # the head rather than assume the tie still holds.
        self.head, self.head_scale = _load_weight(state["lm_head.weight"], quantize)
        self.reset()

    def weight_bytes(self) -> int:
        """Bytes actually held by this model's weight arrays and their scales —
        never the biases or LayerNorm vectors, which are not quantized. What
        --quantize buys or costs, measured rather than assumed: array('b') is 1
        byte/element against array('f')'s 4, and a scale array adds 4 bytes per
        output row on top of the int8 rows it belongs to."""
        total = 0
        for rows, scales in self._weight_slots():
            total += sum(len(row) * row.itemsize for row in rows)
            if scales is not None:
                total += len(scales) * scales.itemsize
        return total

    def _weight_slots(self):
        """Every (rows, scales) pair weight_bytes and quantize_model_report walk."""
        yield self.wte, self.wte_scale
        yield self.wpe, self.wpe_scale
        for layer in self.layers:
            yield layer["qkv_w"], layer["qkv_scale"]
            yield layer["attn_out_w"], layer["attn_out_scale"]
            yield layer["fc_w"], layer["fc_scale"]
            yield layer["mlp_out_w"], layer["mlp_out_scale"]
        yield self.head, self.head_scale

    def total_params(self) -> int:
        """model.py's total_params(): the tied embedding counted once.

        This is the number SCOREBOARD.md quotes — 10.9M for round 4 — so it is the
        one to print. model.py also has num_params(), which drops the learned
        position table for comparison with older runs; that is 196,608 fewer on
        round 4 and would read 10.7M.
        """
        per_layer = (4 * self.n_embd                                     # two LayerNorms
                     + 3 * self.n_embd * self.n_embd + 3 * self.n_embd   # c_attn
                     + self.n_embd * self.n_embd + self.n_embd           # attn c_proj
                     + 4 * self.n_embd * self.n_embd + 4 * self.n_embd   # c_fc
                     + 4 * self.n_embd * self.n_embd + self.n_embd)      # mlp c_proj
        return (self.vocab_size * self.n_embd + self.block_size * self.n_embd
                + self.n_layer * per_layer + 2 * self.n_embd)

    def reset(self, keep_counters: bool = False):
        # Keys are kept one row per token, because a score is q . k for one k.
        # Values are kept one COLUMN per head dimension, because the attended
        # output's dimension j is sum over time of weight * value[j]: stored
        # this way, that is one dot product per dimension instead of a Python
        # loop over time and dimension together.
        self.keys = [[[] for _ in range(self.n_head)] for _ in range(self.n_layer)]
        self.values = [[[[] for _ in range(self.head_dim)] for _ in range(self.n_head)]
                       for _ in range(self.n_layer)]
        if self.quantize_kv:
            # One scale per cached key vector, and one per cached value vector
            # (shared by that vector's head_dim columns above) — see step().
            self.key_scales = [[[] for _ in range(self.n_head)] for _ in range(self.n_layer)]
            self.value_scales = [[[] for _ in range(self.n_head)] for _ in range(self.n_layer)]
        self.history = []
        if not keep_counters:
            self.rebuilt = 0          # window re-prefills, for the caller to report
            self.stopped_at_context = False

    def window_keep(self, exact_window: bool = False, keep: int | None = None) -> int:
        """How many of the latest tokens a refill carries over when the window fills.

        exact_window: block_size - 1, which is torch's uncached sampler exactly --
        every next token predicted from a fresh forward over the last block_size
        tokens -- and costs a whole window per token once full. Otherwise `keep`,
        by default half the window.
        """
        if exact_window:
            if keep is not None and keep != self.block_size - 1:
                raise ValueError("exact_window keeps block_size - 1 tokens; "
                                 "pass exact_window or keep, not both")
            return self.block_size - 1
        if keep is None:
            return self.block_size // 2
        if not 0 <= keep < self.block_size:
            raise ValueError(f"keep must be between 0 and {self.block_size - 1}")
        return keep

    def step(self, token: int, keep: int | None = None):
        """Feed one token, return the logits for what comes next.

        When the window is already full, the cache is rebuilt first: the last
        `keep` tokens of the history are re-read from position 0 and the new
        token goes in after them. `keep` defaults to block_size - 1, the exact
        window (see window_keep); generate() passes its own.
        """
        if len(self.history) >= self.block_size:
            # REBUILT, NEVER SLID. FINDINGS-kv-cache-2026-09-19.md: "merely
            # deleting old keys would retain hidden states influenced by dropped
            # tokens", and the positions are learned, so a slid cache would also
            # run past the position table (rasbt/LLMs-from-scratch
            # ch04/03_kv-cache asserts "Position embedding overflow" for the same
            # reason). Keeping block_size - 1 tokens is model.generate()'s own
            # behaviour and costs a whole window on EVERY token past it: 7.4 s
            # on the ctx-128 arms and 109.8 s on round 4, measured 2026-09-20.
            # Keeping fewer is the refill: one re-read of `keep` tokens buys
            # block_size - keep new ones before the next.
            kept = self.block_size - 1 if keep is None else keep
            self.rebuilt += 1
            tail = self.history[len(self.history) - kept:]
            self.reset(keep_counters=True)
            for earlier in tail:
                self.step(earlier)
        position = len(self.history)
        self.history.append(token)
        x = [a + b for a, b in zip(_embed_row(self.wte, self.wte_scale, token),
                                    _embed_row(self.wpe, self.wpe_scale, position))]
        scale = 1.0 / math.sqrt(self.head_dim)
        # Looked up once per step, and at call time rather than bound at import,
        # so a test can put either arithmetic under the same model.
        dot, attend = _dot, _attend
        quantize, quantize_kv = self.quantize, self.quantize_kv
        width = self.n_embd
        for index, layer in enumerate(self.layers):
            def project(prefix, value):
                # Dispatches once per call on the model's own --quantize flag,
                # never per element; the unquantized branch calls the same
                # _matvec every non-quantized model has always called.
                if quantize:
                    return _matvec_int8(layer[prefix + "_w"], layer[prefix + "_scale"],
                                        value, layer[prefix + "_b"])
                return _matvec(layer[prefix + "_w"], value, layer[prefix + "_b"])

            h = _layernorm(x, layer["ln1_w"], layer["ln1_b"])
            qkv = project("qkv", h)
            attended = [0.0] * width
            for head in range(self.n_head):
                lo, hi = head * self.head_dim, (head + 1) * self.head_dim
                q = qkv[lo:hi]
                past_k, columns = self.keys[index][head], self.values[index][head]
                new_k = qkv[width + lo: width + hi]
                new_v = qkv[2 * width + lo: 2 * width + hi]
                if quantize_kv:
                    kq, kscale = _quantize_row(new_k)
                    past_k.append(kq)
                    key_scales = self.key_scales[index][head]
                    key_scales.append(kscale)
                    vq, vscale = _quantize_row(new_v)
                    for column, v in zip(columns, vq):
                        column.append(v)
                    value_scales = self.value_scales[index][head]
                    value_scales.append(vscale)
                    scores = [dot(q, k) * ks * scale for k, ks in zip(past_k, key_scales)]
                    top = max(scores)
                    weights = [math.exp(s - top) for s in scores]
                    attended[lo:hi] = _attend_int8(weights, columns, value_scales)
                else:
                    past_k.append(new_k)
                    for column, value in zip(columns, new_v):
                        column.append(value)
                    scores = [dot(q, k) * scale for k in past_k]
                    top = max(scores)
                    attended[lo:hi] = attend([math.exp(s - top) for s in scores], columns)
            projected = project("attn_out", attended)
            x = [a + b for a, b in zip(x, projected)]
            h = _layernorm(x, layer["ln2_w"], layer["ln2_b"])
            inner = _gelu(project("fc", h))
            out = project("mlp_out", inner)
            x = [a + b for a, b in zip(x, out)]
        h = _layernorm(x, self.ln_f_w, self.ln_f_b)
        if self.head_scale is None:
            return [dot(row, h) for row in self.head]   # lm_head has no bias
        return [dot(row, h) * s for row, s in zip(self.head, self.head_scale)]

    def generate(self, ids, max_new_tokens: int, temperature: float = 0.8,
                 top_k: int | None = 40, seed: int | None = None,
                 past_context: bool = True, exact_window: bool = False,
                 keep: int | None = None):
        """Sample tokens, past the context window by refilling it.

        WHAT HAPPENS AT THE WINDOW. Once block_size tokens are in, the next one
        first clears the cache and re-reads the last `keep` tokens (half the
        window unless told otherwise), then carries on until the window is full
        again. Each refill costs `keep` steps and buys block_size - keep tokens,
        so past the window a token costs about twice what it costs inside it,
        instead of a whole window each. The price is the context: right after a
        refill a token sees `keep` earlier tokens, just before the next it sees
        block_size - 1, where torch's sampler always shows it block_size - 1. So
        past the window this is NOT torch's text. exact_window=True keeps
        block_size - 1 at every refill, which is torch's uncached crop token for
        token and the mode the parity tests run in; it costs a whole window per
        token past the line (7.4 s at context 128, 110 s at 512, before sumprod).

        past_context=False stops at the window instead, so the prompt and the
        text together fit in one window; `stopped_at_context` records that and
        `rebuilt` counts refills. A prompt longer than the window is cut to its
        last block_size tokens before reading: that is exactly the state the
        exact window would reach token by token, without the per-token wall.

        This is list(iter_generate(...)): the same tokens, all at once.
        """
        return list(self.iter_generate(ids, max_new_tokens, temperature, top_k, seed,
                                       past_context, exact_window, keep))

    def iter_generate(self, ids, max_new_tokens: int, temperature: float = 0.8,
                      top_k: int | None = 40, seed: int | None = None,
                      past_context: bool = True, exact_window: bool = False,
                      keep: int | None = None):
        """generate(), one token id at a time, each yielded as soon as it is chosen.

        The arguments are checked HERE, when this is called, not when the first
        token is asked for, so a caller learns about a bad temperature before it
        starts a thread to read the tokens. The prompt is read on the first
        next(), which is the slow part before the first token.

        The last token is yielded and never fed back: its logits would be for a
        token nobody asked for, and past the window feeding it could cost a whole
        refill. So after the loop `history` ends one token short of the text, and
        `rebuilt` counts only refills that produced something. (Streamed after
        the pattern of generate_text_basic_stream in rasbt/LLMs-from-scratch,
        ch05/13_olmo3, which yields each token while the caller prints it.)
        """
        if temperature < 0 or not math.isfinite(temperature):
            raise ValueError("temperature must be finite and nonnegative")
        if max_new_tokens < 0 or (top_k is not None and top_k < 1):
            raise ValueError("max_new_tokens must be nonnegative and top_k positive")
        if not ids:
            raise ValueError("generation needs at least one token")
        keep = self.window_keep(exact_window, keep)
        return self._produce(list(ids), max_new_tokens, temperature, top_k,
                             random.Random(seed), past_context, keep)

    def _produce(self, ids, max_new_tokens, temperature, top_k, rng, past_context, keep):
        logits = None
        for token in ids[-self.block_size:]:
            logits = self.step(token, keep)
        room = self.block_size - len(self.history)
        if not past_context and max_new_tokens > room:
            self.stopped_at_context = True
            max_new_tokens = max(room, 0)
        for n in range(max_new_tokens):
            if temperature == 0:
                nxt = max(range(len(logits)), key=logits.__getitem__)
            else:
                scaled = [value / temperature for value in logits]
                if top_k is not None:
                    # model.py masks logits strictly below the k-th largest, which
                    # keeps every tie at the boundary. Same rule here.
                    cut = sorted(scaled, reverse=True)[min(top_k, len(scaled)) - 1]
                    scaled = [v if v >= cut else -math.inf for v in scaled]
                top = max(scaled)
                weights = [math.exp(v - top) if v > -math.inf else 0.0 for v in scaled]
                nxt = rng.choices(range(len(weights)), weights=weights, k=1)[0]
            yield nxt
            if n + 1 < max_new_tokens:
                logits = self.step(nxt, keep)


def checkpoint_exists(out_dir) -> bool:
    """checkpoint.py's rule: half a checkpoint is not a checkpoint."""
    out = Path(out_dir)
    return (out / "ckpt.pt").is_file() and (out / "tokenizer.json").is_file()


def load_checkpoint(out_dir, quantize: bool = False, quantize_kv: bool = False):
    """Return (model, tokenizer, config) ready to generate from, without torch.

    quantize and quantize_kv default False and pass straight through to
    PlainGPT — see its docstring and _quantize_row above for what each does.
    """
    out = Path(out_dir)
    weights, vocab = out / "ckpt.pt", out / "tokenizer.json"
    missing = [str(p) for p in (weights, vocab) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"no trained model in {out}/ — missing {', '.join(missing)}. "
            f"Train one first, or point at the directory a previous run wrote.")
    config, state = _read(weights)
    tok = CharTokens.load(vocab)
    # checkpoint.py catches this at load for the same reason: a tokenizer that
    # disagrees with the embedding table generates index errors or silent garbage,
    # and naming both numbers here is cheaper than debugging either later.
    if tok.vocab_size != config["vocab_size"]:
        raise _Refused(
            f"{out}/ is inconsistent: tokenizer has {tok.vocab_size} tokens but the "
            f"model's vocab_size is {config['vocab_size']}. The tokenizer and the "
            f"weights came from different training runs.")
    return PlainGPT(config, state, quantize=quantize, quantize_kv=quantize_kv), tok, config


def sample(model, tok, prompt: str, tokens: int = 400, temperature: float = 0.8,
           top_k: int | None = 40, seed: int | None = None,
           past_context: bool = True, exact_window: bool = False,
           keep: int | None = None) -> str:
    """Prompt in, text out, including the prompt — checkpoint.sample's shape.

    An empty prompt, or one made only of characters this model never saw, encodes
    to nothing; falling back to token 0 keeps that producing text rather than an
    error, which is what checkpoint.py does too, and it is what
    test_checkpoint.test_prompt_of_unknown_characters_does_not_crash pins down on
    that side. The fallback is silent by construction, so a caller that wants to
    name what was lost asks tok.unknown_characters(prompt) first; main() does.

    The default `tokens=400` is past the window of every ctx-128 checkpoint in
    this repository, and generate() refills the window to get there (see its
    docstring for what that costs in context); `model.rebuilt` counts refills.
    exact_window=True is torch's sampler token for token, at a whole window per
    token past the line.
    """
    ids = tok.encode(prompt) or [0]
    model.reset()
    return tok.decode(ids + model.generate(ids, tokens, temperature=temperature,
                                           top_k=top_k, seed=seed,
                                           past_context=past_context,
                                           exact_window=exact_window, keep=keep))


def stream(model, tok, prompt: str, tokens: int = 400, temperature: float = 0.8,
           top_k: int | None = 40, seed: int | None = None,
           past_context: bool = True, exact_window: bool = False,
           keep: int | None = None):
    """sample(), a piece at a time: "".join(stream(...)) == sample(...) for a seed.

    The first piece is the prompt as the model will read it (what encode() kept,
    or the fallback token), yielded before the model reads it; then one decoded
    token per piece, each as soon as it is chosen. A character tokenizer decodes
    each id on its own, so no piece is ever half a character. Arguments are
    checked when this is called. Stop early by closing the iterator or simply
    no longer asking: nothing runs between pieces.
    """
    ids = tok.encode(prompt) or [0]
    model.reset()
    produced = model.iter_generate(ids, tokens, temperature=temperature, top_k=top_k,
                                   seed=seed, past_context=past_context,
                                   exact_window=exact_window, keep=keep)
    return _pieces(tok, ids, produced)


def _pieces(tok, ids, produced):
    yield tok.decode(ids)
    for nxt in produced:
        yield tok.decode([nxt])


def unknown_note(tok, prompt: str, what: str = "your prompt") -> str:
    """The sentence to show BEFORE generating when encode() will drop characters.

    "" when nothing is dropped. Shared by main() and home.py so the window and
    the command line say the same thing in the same words.

    A STRANGER'S PROMPT IS THE LIKELIEST PLACE THIS MODEL'S VOCABULARY RUNS OUT.
    Train on English, then type a line in your own script or with your word
    processor's curly quotes, and every one of those characters is missing from
    the 82 the included model knows. encode() drops them without a word, so the
    text that comes back answers a prompt nobody typed unless something says so.
    """
    unknown = tok.unknown_characters(prompt)
    if not unknown:
        return ""
    lost, total = sum(unknown.values()), len(prompt)
    shown = list(unknown)[:12]
    names = ", ".join(repr(c) for c in shown)
    if len(unknown) > len(shown):
        names += f", and {len(unknown) - len(shown)} more"
    tail = ("" if lost < total else
            " Nothing was left of it, so it starts from the first character it "
            "knows instead.")
    return (f"This model never saw {len(unknown)} of the characters in {what} "
            f"({names}), {lost} of its {total} characters in all. They are "
            f"dropped before it writes, so the text continues what was left.{tail}")


def main() -> int:
    ap = argparse.ArgumentParser(description="write text from a locallm checkpoint "
                                             "using only the standard library")
    ap.add_argument("--out", default="out", help="model dir holding ckpt.pt + tokenizer.json")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--tokens", type=int, default=200)
    ap.add_argument("--temperature", type=float, default=0.8,
                    help="0 decodes greedily and is the one comparable to torch")
    ap.add_argument("--top-k", type=int, default=40)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--exact-window", action="store_true",
                    help="past the context window, predict every token from the "
                         "full window, as torch does; identical to torch's text, "
                         "but each token past the window re-reads the whole window "
                         "(seconds to minutes each)")
    ap.add_argument("--keep", type=int, default=None,
                    help="past the window, how many of the latest tokens a refill "
                         "keeps (default half the window)")
    ap.add_argument("--stop-at-window", action="store_true",
                    help="stop when the prompt and the text fill one window")
    ap.add_argument("--quantize", action="store_true",
                    help="hold weights as int8 (one scale per row) instead of "
                         "float32 -- about a quarter the memory, off by default "
                         "because greedy output can then disagree with float32's")
    ap.add_argument("--quantize-kv", action="store_true",
                    help="hold the key/value cache as int8 the same way, off by "
                         "default for the same reason")
    # The default since 2026-09-26; kept so command lines written before still run.
    ap.add_argument("--past-context", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    try:
        model, tok, config = load_checkpoint(args.out, quantize=args.quantize,
                                             quantize_kv=args.quantize_kv)
    except zipfile.BadZipFile as exc:
        # zipfile's own message is "File is not a zip file" with no path in it,
        # which in a stick's console is indistinguishable from any other failure.
        print(f"plain_generate: {Path(args.out) / 'ckpt.pt'} is not a torch.save "
              f"archive ({exc})", file=sys.stderr)
        return 1
    except (_Refused, FileNotFoundError) as exc:
        print(f"plain_generate: {exc}", file=sys.stderr)
        return 1
    print(f"{model.total_params():,} numbers, {tok.vocab_size} vocabulary entries, "
          f"context {config['block_size']} — no torch, no numpy", file=sys.stderr)
    if args.quantize or args.quantize_kv:
        print(f"plain_generate: weights held as {model.weight_bytes():,} bytes "
              f"({'int8' if args.quantize else 'float32'} weights, "
              f"{'int8' if args.quantize_kv else 'float32'} KV cache)", file=sys.stderr)
    note = unknown_note(tok, args.prompt)
    if note:
        # Said before generating, not after: the answer takes seconds to come.
        print(f"plain_generate: {note}", file=sys.stderr)
    try:
        pieces = stream(model, tok, args.prompt, args.tokens,
                        temperature=args.temperature, top_k=args.top_k, seed=args.seed,
                        past_context=not args.stop_at_window,
                        exact_window=args.exact_window, keep=args.keep)
    except ValueError as exc:
        print(f"plain_generate: {exc}", file=sys.stderr)
        return 2
    keep = model.window_keep(args.exact_window, args.keep)
    # Printed as it is written, the same bytes print(sample(...)) would give at
    # the end: a 200-token answer is half a minute, and a blank terminal for
    # that long reads as a hang.
    for piece in pieces:
        sys.stdout.write(piece)
        sys.stdout.flush()
    sys.stdout.write("\n")
    if model.stopped_at_context:
        # Silently returning short text would read as the model running out of
        # things to say, which is a different claim from hitting its window.
        print(f"plain_generate: stopped at this model's {config['block_size']}-token "
              f"context window, as --stop-at-window asked", file=sys.stderr)
    if model.rebuilt:
        how = ("the whole window each time, as torch does" if args.exact_window else
               f"keeping the last {keep} tokens each time, so text past the window "
               f"saw between {keep} and {config['block_size'] - 1} earlier tokens "
               f"rather than torch's {config['block_size'] - 1}; --exact-window "
               f"matches torch")
        times = "once" if model.rebuilt == 1 else f"{model.rebuilt} times"
        print(f"plain_generate: refilled the context window {times}, {how}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
