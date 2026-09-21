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
costs ~13.0M multiply-accumulates per token at full context. Measured on this
machine, plain CPython does ~48M of them per second through
`sum(map(mul, row, x))` over `array('f')` rows, and the module below measures
199 ms per token on that checkpoint and 93 ms on the 4.9M one. That is slow and
it is not nothing: a 200-token answer in 51 seconds, from a stick, on a computer
with no machine-learning software on it.

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

    def __init__(self, chars):
        self.chars = list(chars)
        self._index = {c: i for i, c in enumerate(self.chars)}

    @property
    def vocab_size(self) -> int:
        return len(self.chars)

    def encode(self, text: str):
        return [self._index[c] for c in text if c in self._index]

    def decode(self, ids) -> str:
        return "".join(self.chars[int(i)] for i in ids)

    @classmethod
    def load(cls, path):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
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


def _matvec(rows, x, bias):
    return [sum(map(mul, row, x)) + b for row, b in zip(rows, bias)]


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
    difference between 199 ms and tens of seconds per token, so unlike
    model.py's opt-in `use_cache` it is not optional here.
    """

    def __init__(self, config, state):
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
        if "transformer.wpe.weight" not in state:
            raise _Refused("no learned position table; this is not a gpt-core checkpoint")
        self.wte = _rows(state["transformer.wte.weight"])
        self.wpe = _rows(state["transformer.wpe.weight"])
        self.layers = []
        for i in range(self.n_layer):
            p = f"transformer.h.{i}."
            self.layers.append({
                "ln1_w": _vector(state[p + "ln_1.weight"]),
                "ln1_b": _vector(state[p + "ln_1.bias"]),
                "ln2_w": _vector(state[p + "ln_2.weight"]),
                "ln2_b": _vector(state[p + "ln_2.bias"]),
                "qkv_w": _rows(state[p + "attn.c_attn.weight"]),
                "qkv_b": _vector(state[p + "attn.c_attn.bias"]),
                "attn_out_w": _rows(state[p + "attn.c_proj.weight"]),
                "attn_out_b": _vector(state[p + "attn.c_proj.bias"]),
                "fc_w": _rows(state[p + "mlp.c_fc.weight"]),
                "fc_b": _vector(state[p + "mlp.c_fc.bias"]),
                "mlp_out_w": _rows(state[p + "mlp.c_proj.weight"]),
                "mlp_out_b": _vector(state[p + "mlp.c_proj.bias"]),
            })
        self.ln_f_w = _vector(state["transformer.ln_f.weight"])
        self.ln_f_b = _vector(state["transformer.ln_f.bias"])
        # Tied to wte in model.py, but a checkpoint records both names, so read
        # the head rather than assume the tie still holds.
        self.head = _rows(state["lm_head.weight"])
        self.reset()

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
        self.keys = [[[] for _ in range(self.n_head)] for _ in range(self.n_layer)]
        self.values = [[[] for _ in range(self.n_head)] for _ in range(self.n_layer)]
        self.history = []
        if not keep_counters:
            self.rebuilt = 0          # window re-prefills, for the caller to report
            self.stopped_at_context = False

    def step(self, token: int):
        """Feed one token, return the logits for what comes next."""
        if len(self.history) >= self.block_size:
            # Same as model.generate()'s cached path, and deliberately so:
            # FINDINGS-kv-cache-2026-09-19.md, "once the context fills, generation
            # rebuilds the cache from the retained window on every step", because
            # "merely deleting old keys would retain hidden states influenced by
            # dropped tokens and change the old model's sliding-window behavior".
            # So every token past the window costs a whole window, which under
            # torch is one batched forward and here is 7.4 s on the ctx-128 arms
            # and 109.8 s on round 4. Sliding the window would make this a
            # different model, so generate() stops at the line instead.
            self.rebuilt += 1
            tail = self.history[-(self.block_size - 1):]
            self.reset(keep_counters=True)
            for earlier in tail:
                self.step(earlier)
        position = len(self.history)
        self.history.append(token)
        x = [a + b for a, b in zip(self.wte[token], self.wpe[position])]
        scale = 1.0 / math.sqrt(self.head_dim)
        for index, layer in enumerate(self.layers):
            h = _layernorm(x, layer["ln1_w"], layer["ln1_b"])
            qkv = _matvec(layer["qkv_w"], h, layer["qkv_b"])
            width = self.n_embd
            attended = [0.0] * width
            for head in range(self.n_head):
                lo, hi = head * self.head_dim, (head + 1) * self.head_dim
                q = qkv[lo:hi]
                past_k, past_v = self.keys[index][head], self.values[index][head]
                past_k.append(qkv[width + lo: width + hi])
                past_v.append(qkv[2 * width + lo: 2 * width + hi])
                scores = [sum(map(mul, q, k)) * scale for k in past_k]
                top = max(scores)
                weights = [math.exp(s - top) for s in scores]
                norm = 1.0 / sum(weights)
                accumulated = [0.0] * self.head_dim
                for weight, value in zip(weights, past_v):
                    weight *= norm
                    for j in range(self.head_dim):
                        accumulated[j] += weight * value[j]
                attended[lo:hi] = accumulated
            projected = _matvec(layer["attn_out_w"], attended, layer["attn_out_b"])
            x = [a + b for a, b in zip(x, projected)]
            h = _layernorm(x, layer["ln2_w"], layer["ln2_b"])
            inner = _gelu(_matvec(layer["fc_w"], h, layer["fc_b"]))
            out = _matvec(layer["mlp_out_w"], inner, layer["mlp_out_b"])
            x = [a + b for a, b in zip(x, out)]
        h = _layernorm(x, self.ln_f_w, self.ln_f_b)
        return [sum(map(mul, row, h)) for row in self.head]   # lm_head has no bias

    def generate(self, ids, max_new_tokens: int, temperature: float = 0.8,
                 top_k: int | None = 40, seed: int | None = None,
                 past_context: bool = False):
        """Sample tokens, stopping at the context window unless past_context.

        Stopping there is not a limitation of this implementation, it is the price
        of matching model.py's cached path: every token past the window costs a
        full re-prefill of the window, so on the ctx-128 checkpoints a 200-token
        request spends minutes on each of its last 72 tokens. Set past_context
        when that is genuinely wanted; `stopped_at_context` records the clamp and
        `rebuilt` counts the re-prefills.
        """
        if temperature < 0 or not math.isfinite(temperature):
            raise ValueError("temperature must be finite and nonnegative")
        if max_new_tokens < 0 or (top_k is not None and top_k < 1):
            raise ValueError("max_new_tokens must be nonnegative and top_k positive")
        if not ids:
            raise ValueError("generation needs at least one token")
        rng = random.Random(seed)
        logits = None
        for token in ids:
            logits = self.step(token)
        room = self.block_size - len(self.history)
        if not past_context and max_new_tokens > room:
            self.stopped_at_context = True
            max_new_tokens = max(room, 0)
        produced = []
        for _ in range(max_new_tokens):
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
            produced.append(nxt)
            logits = self.step(nxt)
        return produced


def checkpoint_exists(out_dir) -> bool:
    """checkpoint.py's rule: half a checkpoint is not a checkpoint."""
    out = Path(out_dir)
    return (out / "ckpt.pt").is_file() and (out / "tokenizer.json").is_file()


def load_checkpoint(out_dir):
    """Return (model, tokenizer, config) ready to generate from, without torch."""
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
    return PlainGPT(config, state), tok, config


def sample(model, tok, prompt: str, tokens: int = 400, temperature: float = 0.8,
           top_k: int | None = 40, seed: int | None = None,
           past_context: bool = False) -> str:
    """Prompt in, text out, including the prompt — checkpoint.sample's shape.

    An empty prompt, or one made only of characters this model never saw, encodes
    to nothing; falling back to token 0 keeps that producing text rather than an
    error, which is what checkpoint.py does too. The default `tokens=400` is past
    the window of every ctx-128 checkpoint in this repository, which is why
    generate() clamps rather than grinding; read `model.stopped_at_context` after.
    """
    ids = tok.encode(prompt) or [0]
    model.reset()
    return tok.decode(ids + model.generate(ids, tokens, temperature=temperature,
                                           top_k=top_k, seed=seed,
                                           past_context=past_context))


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
    ap.add_argument("--past-context", action="store_true",
                    help="keep going past the context window; every token after it "
                         "re-runs the whole window, which is minutes each")
    args = ap.parse_args()
    try:
        model, tok, config = load_checkpoint(args.out)
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
    print(sample(model, tok, args.prompt, args.tokens, temperature=args.temperature,
                 top_k=args.top_k, seed=args.seed, past_context=args.past_context))
    if model.stopped_at_context:
        # Silently returning short text would read as the model running out of
        # things to say, which is a different claim from hitting its window.
        print(f"plain_generate: stopped at this model's {config['block_size']}-token "
              f"context window rather than re-running it per token; "
              f"--past-context overrides", file=sys.stderr)
    if model.rebuilt:
        print(f"plain_generate: re-prefilled the window {model.rebuilt} times",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
