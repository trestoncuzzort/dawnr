"""Corpus-built character or byte-BPE tokenizers, document splits and batching.

Neither tokenizer downloads pretrained vocabulary or weights. Character mode
needs only the standard library; optional byte-BPE uses the tokenizers package.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import torch

DOC_MARKER = "\n\n# file: "


def documents(text: str) -> list[str]:
    """Split a corpus into documents.

    Uses make_corpus.py's `# file:` markers when present, otherwise falls back to
    blank-line-separated blocks so arbitrary user text is still grouped rather
    than sliced mid-sentence.
    """
    if DOC_MARKER in text:
        head, *rest = text.split(DOC_MARKER)
        docs = ([head] if head.strip() else []) + ["# file: " + r for r in rest]
    else:
        docs = text.split("\n\n")
    return [d for d in docs if d.strip()]


def group_split(text: str, val_frac: float = 0.1, seed: int = 1337) -> tuple[str, str]:
    """Split by whole document, never mid-document, after removing duplicates.

    The naive alternative is to cut the corpus at 90% of its length. That splits
    in the middle of a document and, worse, lets duplicated material sit on both
    sides of the split, so validation measures memorisation instead of
    generalisation. See leakage.py, which will tell you how bad it is.

    Assignment is by hash of the document text, so it is deterministic, and two
    identical documents always land on the same side even if de-duplication is
    skipped.
    """
    seen, docs = set(), []
    for d in documents(text):
        key = hashlib.sha1(d.encode("utf-8")).hexdigest()
        if key in seen:
            continue          # exact duplicate: keep one copy, in one split
        seen.add(key)
        docs.append((key, d))

    total = sum(len(d) for _, d in docs)
    target = total * val_frac

    # Two passes, both bounded by the target.
    #
    # Pass 1 walks the documents in a SEED-SHUFFLED order and takes any that
    # still fit. That is what makes `seed` real: a different seed produces a
    # genuinely different validation set, which is the only way to measure how
    # much of a result is split-induced rather than model-induced.
    #
    # Pass 2 fills the leftover gap smallest-first. Without it, one early large
    # document can consume the budget and leave validation far short of target.
    # Never "add until the target is passed": one document bigger than the whole
    # target would land in validation and take most of the corpus with it.
    rng = random.Random(seed)
    order = list(docs)
    rng.shuffle(order)

    val, acc, leftover = [], 0, []
    for key, d in order:
        if acc + len(d) <= target:
            val.append(d)
            acc += len(d)
        else:
            leftover.append((key, d))

    train = []
    for key, d in sorted(leftover, key=lambda kv: len(kv[1])):
        if acc + len(d) <= target:
            val.append(d)
            acc += len(d)
        else:
            train.append(d)

    if not train:                            # tiny corpora: never empty the train side
        train, val = val, []
    return "\n\n".join(train), "\n\n".join(val)


def _unique_docs(text: str) -> list[str]:
    """The documents group_split actually splits: deduplicated, in order."""
    seen, out = set(), []
    for d in documents(text):
        key = hashlib.sha1(d.encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def achievable_val_frac(lengths: list[int], val_frac: float) -> float:
    """Best validation fraction ANY whole-document split could reach.

    Subset-sum over document lengths, largest total not exceeding the target.
    This is the number the old boolean was groping for: it separates "the
    splitter did badly" from "no splitter could do better on this corpus".
    Quantised when the corpus is large so the bitset stays cheap.
    """
    total = sum(lengths)
    if total == 0:
        return 0.0
    target = int(total * val_frac)
    scale = max(1, total // 200_000)          # bound the bitset width
    bits, tgt = 1, target // scale
    for w in lengths:
        bits |= bits << max(1, w // scale)
        bits &= (1 << (tgt + 1)) - 1          # nothing above target can help
    best = bits.bit_length() - 1
    return (best * scale) / total


def split_health(text: str, val_frac: float = 0.1, seed: int = 1337) -> dict:
    """What this corpus can support, in numbers. No verdict.

    THIS USED TO REPORT ON A DIFFERENT CORPUS THAN THE ONE IT SPLIT. It counted
    documents and measured the largest document BEFORE deduplication, while
    group_split dedupes FIRST. On 50 copies of one document plus 5 unique ones it
    reported "55 documents, largest 2.5%" when the truth was 7 documents with one
    dominating the mass - both printed diagnostics pointed away from the cause.

    The boolean is gone too. One bit conflated "corpus too lumpy to split"
    (remedy: more, smaller documents) with "val set too small to estimate
    anything" (remedy: raise val_frac or shrink block_size), and its 0.5
    tolerance was an eyeballed number that served neither. Two ratios replace it:

        achieved / achievable  - how well the SPLITTER did
        achievable / requested - whether the CORPUS can support the request

    A caller that wants a hard stop should derive it from what the number feeds:
    val_chars // block_size is the usable-precision floor, and get_batch already
    raises below that floor by construction.
    """
    train_text, val_text = group_split(text, val_frac, seed)
    total = len(train_text) + len(val_text)
    achieved = len(val_text) / max(total, 1)
    docs = _unique_docs(text)
    lengths = [len(d) for d in docs]
    uniq_total = sum(lengths) or 1
    achievable = achievable_val_frac(lengths, val_frac)
    return {
        "unique_documents": len(docs),
        "requested_val_frac": val_frac,
        "achieved_val_frac": achieved,
        "achievable_val_frac": achievable,
        "largest_unique_doc_frac": max(lengths, default=0) / uniq_total,
        "val_documents": len(_unique_docs(val_text)),
        "val_chars": len(val_text),
    }


# How close to the requested split counts as "close enough". A holdout that
# reaches 80% of what was asked for measures the same thing as one that reaches
# 100%; the difference does not change what the number means, and warning about
# it trains the user to ignore the warning.
#
# The number is not decoration. Both ratios below are subset-sum and greedy
# results bounded BELOW the request, so an exact `<` comparison is true on
# almost every healthy corpus: measured here, 100 uniform documents report
# achieved == achievable to four digits and still fail an exact `<`, and a
# 200-document corpus failed BOTH exact tests. Three callers each rolled their
# own subset of this test against those raw ratios; two of them dropped the
# corpus arm entirely. The result was a check that cried wolf on good corpora
# and stayed silent on the one shape it exists to catch — a single document
# holding most of the text. One function now, so the three cannot drift again.
SPLIT_CLOSE_ENOUGH = 0.8

# Both ratios are computed, not measured, so a threshold comparison lands on
# float artefacts: 0.1 * 0.8 is 0.08000000000000002, which makes an achievable
# fraction of exactly 0.08 - the documented cutoff - compare as BELOW it. One
# epsilon, applied once, at the only place the threshold is used.
_SPLIT_EPS = 1e-9


def split_verdict(h: dict) -> str | None:
    """Why this split cannot carry a validation claim, or None if it can.

    Takes a split_health() dict. Returns:

      "empty"    - nothing was held back at all; there is no validation number
      "corpus"   - the shortfall is the corpus's: no whole-document split of it
                   could get near the request. Remedy: more, smaller documents
      "splitter" - the shortfall is this split's: the corpus could have reached
                   the request. Remedy: another seed
      None       - the holdout is close enough to what was asked for

    ONE question is asked against the REQUEST — "is the holdout that was actually
    produced close enough to the one that was asked for?" — and only then is the
    blame assigned. Testing the second ratio against `achievable` instead would
    compound the tolerance: at 0.8 each, a holdout of 0.64x the requested size
    passes both tests and is silently trusted, which is not what the constant
    above says. The blame arm decides the REMEDY; it does not get a second,
    looser say in whether there is a problem at all.
    """
    if h["val_chars"] == 0:
        return "empty"
    floor = h["requested_val_frac"] * SPLIT_CLOSE_ENOUGH
    if h["achieved_val_frac"] >= floor - _SPLIT_EPS:
        return None
    # It fell short. Could ANY whole-document split of this corpus have made it?
    if h["achievable_val_frac"] < floor - _SPLIT_EPS:
        return "corpus"
    return "splitter"


# WHAT A CAPACITY FAILURE SAYS, lowercased, from the backends this runs on.
# torch.cuda.OutOfMemoryError is matched by TYPE, which is the honest primary;
# these three substrings are for the backends that raise a plain RuntimeError:
#
#   "CUDA out of memory. Tried to allocate 2.00 GiB (GPU 0; ...)"  out of memory
#   "MPS backend out of memory (MPS allocated: 9.06 GB, ...)"      out of memory
#   "[enforce fail at alloc_cpu.cpp:75] . DefaultCPUAllocator:
#    not enough memory: you tried to allocate 4294967296 bytes"    not enough memory
#   "cudaErrorMemoryAllocation"                                    alloc
#
# The list is deliberately short and deliberately about MEMORY. It is a
# whitelist, not a blacklist: anything it does not recognise is not called a
# capacity problem, which is the direction that cannot invent a cause.
_CAPACITY_TELLS = ("out of memory", "not enough memory", "alloc")


def _is_capacity_error(e: BaseException) -> bool:
    """Is this the corpus not fitting, or is it something else entirely?"""
    if isinstance(e, torch.cuda.OutOfMemoryError):
        return True
    msg = str(e).lower()
    return any(tell in msg for tell in _CAPACITY_TELLS)


class CharTokenizer:
    def __init__(self, chars):
        self.chars = list(chars)
        self.stoi = {c: i for i, c in enumerate(self.chars)}
        self.itos = {i: c for i, c in enumerate(self.chars)}

    @property
    def vocab_size(self) -> int:
        return len(self.chars)

    @classmethod
    def from_text(cls, text: str) -> "CharTokenizer":
        return cls(sorted(set(text)))

    def encode(self, s: str):
        return [self.stoi[c] for c in s if c in self.stoi]

    def decode(self, ids) -> str:
        return "".join(self.itos[int(i)] for i in ids)

    def save(self, path):
        Path(path).write_text(json.dumps(self.chars, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path) -> "CharTokenizer":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))


class BPETokenizer:
    """Byte-level BPE learned from local text, with a complete 256-byte alphabet.

    No pretrained vocabulary or normalization: code whitespace and previously
    unseen Unicode survive encoding. The optional tokenizers library only learns
    merges from the supplied training text.
    """
    def __init__(self, backend, training: dict | None = None):
        self.backend = backend
        self.training = training or {}

    @property
    def vocab_size(self) -> int:
        return self.backend.get_vocab_size()

    @classmethod
    def from_text(cls, text: str, vocab_size: int = 8192, min_frequency: int = 2):
        if not text:
            raise ValueError("BPE needs nonempty training text")
        if vocab_size < 256:
            raise ValueError("byte-level BPE needs at least 256 vocabulary entries")
        if min_frequency < 1:
            raise ValueError("min_frequency must be positive")
        try:
            from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers
        except ImportError as exc:
            raise RuntimeError("BPE needs the optional tokenizers package: pip install tokenizers") from exc
        backend = Tokenizer(models.BPE())
        backend.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
        backend.decoder = decoders.ByteLevel()
        trainer = trainers.BpeTrainer(vocab_size=vocab_size, min_frequency=min_frequency,
            initial_alphabet=pre_tokenizers.ByteLevel.alphabet(), show_progress=False)
        # Whole documents preserve whitespace and prevent merges spanning documents.
        backend.train_from_iterator(documents(text), trainer=trainer)
        result = cls(backend, {"text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                               "requested_vocab_size": vocab_size, "min_frequency": min_frequency})
        if result.decode(result.encode(text)) != text:
            raise ValueError("trained tokenizer did not preserve its input text")
        return result

    def encode(self, text: str) -> list[int]:
        return self.backend.encode(text, add_special_tokens=False).ids

    def decode(self, ids) -> str:
        return self.backend.decode([int(i) for i in ids], skip_special_tokens=False)

    def save(self, path):
        payload = {"format": "locallm-tokenizer", "version": 1, "kind": "byte-bpe",
                   "backend": json.loads(self.backend.to_str()), "training": self.training}
        Path(path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("format") != "locallm-tokenizer" or \
                payload.get("version") != 1 or payload.get("kind") != "byte-bpe":
            raise ValueError("unsupported locallm BPE tokenizer format")
        try:
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise RuntimeError("this checkpoint needs tokenizers: pip install tokenizers") from exc
        return cls(Tokenizer.from_str(json.dumps(payload["backend"])), payload.get("training", {}))


def load_tokenizer(path):
    """Read both historical character vocabularies and versioned BPE vocabularies."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list) and all(isinstance(c, str) for c in payload):
        return CharTokenizer(payload)
    return BPETokenizer.load(path)


def tokenizer_fingerprint(tokenizer) -> str:
    """Identify token IDs and encoding rules, independent of training metadata."""
    if isinstance(tokenizer, CharTokenizer):
        payload = {"kind": "char", "chars": tokenizer.chars}
    elif isinstance(tokenizer, BPETokenizer):
        payload = {"kind": "byte-bpe", "backend": json.loads(tokenizer.backend.to_str())}
    else:
        raise TypeError(f"unsupported tokenizer type: {type(tokenizer).__name__}")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_tokenizer(text: str, kind: str = "char", vocab_size: int = 8192,
                    val_frac: float = 0.1, seed: int = 1337,
                    training_text: str | None = None):
    """Fit on an explicit training partition, or use the historical split rules."""
    if kind == "char":
        return CharTokenizer.from_text(text if training_text is None else training_text)
    if kind == "bpe":
        if training_text is None:
            training_text, _ = group_split(text, val_frac=val_frac, seed=seed)
        return BPETokenizer.from_text(training_text, vocab_size=vocab_size)
    raise ValueError(f"unknown tokenizer kind: {kind}")


class Corpus:
    """Holds train/val splits as token tensors and serves random batches."""

    def __init__(self, text: str, tokenizer: CharTokenizer | BPETokenizer, device: str,
                 val_frac: float = 0.1, grouped: bool = True, seed: int = 1337,
                 validation_text: str | None = None):
        """grouped=True splits by whole document and de-duplicates first, so
        validation text cannot also be training text. grouped=False reproduces
        the naive positional cut; it is kept only so leakage.py can show what
        that costs, and it should not be used for real comparisons."""
        # Explicit partitions have already been grouped by their source builder.
        # Their exact bytes and order are part of the experiment identity.
        self.split_mode = "explicit" if validation_text is not None else ("grouped" if grouped else "positional")
        if validation_text is not None:
            train_text, val_text = text, validation_text
            train_ids = torch.tensor(tokenizer.encode(train_text), dtype=torch.int32)
            val_ids = torch.tensor(tokenizer.encode(val_text), dtype=torch.int32)
        elif grouped:
            train_text, val_text = group_split(text, val_frac, seed)
            train_ids = torch.tensor(tokenizer.encode(train_text), dtype=torch.int32)
            val_ids = torch.tensor(tokenizer.encode(val_text), dtype=torch.int32)
        else:
            data = torch.tensor(tokenizer.encode(text), dtype=torch.int32)
            n = int(len(data) * (1 - val_frac))
            train_ids, val_ids = data[:n], data[n:]
            train_text = val_text = None

        # THE SPLIT THIS RUN ACTUALLY TRAINED ON, kept rather than discarded.
        # Anything that wants to describe the holdout — a baseline, a leakage
        # verdict, a split manifest — must read it from here. The alternative is
        # calling group_split() again at the point of use, which agrees only
        # while every caller happens to pass the same val_frac and seed and
        # silently describes a DIFFERENT holdout the moment one does not. That
        # is a latent-correctness trap, not a hypothetical: the defaults are the
        # only reason the existing callers agree today.
        #
        # None on the ungrouped path: that split is positional over tokens, and
        # it exists only so leakage.py can show what the naive cut costs. A
        # consumer that needs the text must skip the ungrouped case rather than
        # reconstruct it.
        self.train_text = train_text
        self.val_text = val_text

        # THE REQUEST THAT PRODUCED THE SPLIT, kept for the same reason the
        # split itself is. A run record that names the corpus but not the
        # holdout cannot tell two runs on different validation sets apart, and
        # every prereg in this folder asserts an identical holdout across arms.
        # runlog.split_fingerprint turns these three into that record.
        self.val_frac = val_frac
        self.seed = seed
        self.grouped = grouped

        # TWO DEVICES, BECAUSE THERE REALLY ARE TWO. `device` is where batches
        # are DELIVERED, which is where the model lives and never changes.
        # `data_device` is where the corpus tensors actually ended up, which is
        # the same thing right up until the corpus does not fit and _place falls
        # back to host memory. Collapsing them into one attribute is what made
        # that fallback silent.
        self.device = device
        self.data_device = device
        # Keep the corpus resident on the training device. Batches are then cut
        # on-device with one vectorised gather instead of a Python loop plus a
        # host-to-device copy per step, which is the dominant cost at these
        # model sizes: the GPU finishes a 3M-parameter step long before Python
        # can assemble the next batch. int32 halves the residency of int64 and
        # costs one cheap cast per batch (nn.Embedding needs int64 indices).
        self.train = self._place(train_ids)
        self.val = self._place(val_ids)
        if self.train.device.type != self.data_device:
            # The val half fell back after the train half was already placed.
            # Keep the whole corpus on one device, so data_device describes all
            # of it rather than most of it.
            self.train = self.train.to(self.data_device)

    def _place(self, t: torch.Tensor) -> torch.Tensor:
        """Move the corpus to the device, falling back to host memory if it
        does not fit. A corpus large enough to fill VRAM should not cost you
        the ability to train on it.

        THE FALLBACK IS NOT FREE AND IT USED TO BE SILENT. It caught the
        exception, returned the CPU tensor, and left self.device saying "cuda",
        so every consumer -- the run log included -- recorded a GPU run that was
        keeping its corpus in host memory. Two things change under it and
        neither is cosmetic:

          speed        every batch is now cut on the CPU and copied across, so a
                       ms/step recorded from this run is not comparable with one
                       recorded from a run that fitted.
          the RNG      get_batch draws its index with device=d.device. On the
                       fallback that is the CPU generator, not the CUDA one, so
                       the same --seed produces a DIFFERENT training batch
                       sequence. A run that silently changes what it trains on
                       is the one thing this folder exists to make VISIBLE: a
                       recorded fingerprint detects a wrong comparison, it
                       cannot prevent one.

        self.device is deliberately NOT changed to "cpu". The model is still on
        the graphics card, and get_batch's last two lines move each batch to
        self.device precisely because the corpus may not be there; setting it to
        "cpu" would skip that move and hand CPU batches to a CUDA model. The
        object stops lying by gaining a second, accurate attribute, not by
        replacing a true one with a false one.

        ONLY A CAPACITY FAILURE TAKES THIS PATH. The except clause caught every
        RuntimeError and printed one invented cause over all of them: measured,
        RuntimeError("CUDA driver initialization failed, you might not have a
        CUDA gpu") printed "the corpus does not fit on the cuda" and returned a
        CPU tensor, and so did "Torch not compiled with CUDA enabled" and "CUDA
        error: device-side assert triggered". None of those is about size.

        Anything else RE-RAISES rather than falling back with the real message,
        and that is the choice on purpose. The fallback is only a remedy for
        one problem. The MODEL is on that device too: if the device is not
        usable, keeping the corpus in host memory buys nothing and the run dies
        at the first forward pass instead, several screens later, with the
        original cause already scrolled away and a WARNING on the record
        claiming a corpus size problem that never existed. Re-raising loses
        nothing -- the exception is the device's own, with its own message.
        """
        if self.data_device == "cpu":
            return t
        try:
            return t.to(self.data_device)
        except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
            if not _is_capacity_error(e):
                raise
            print(f"WARNING: the corpus does not fit on the {self.device} "
                  f"({type(e).__name__}: {str(e).splitlines()[0][:120]}), so it "
                  f"stays in host memory. Training still runs on the "
                  f"{self.device}, but batches are cut on the CPU and copied "
                  f"across: slower, and drawn from the CPU random stream, so "
                  f"this run is not step-for-step comparable with one whose "
                  f"corpus fitted.")
            self.data_device = "cpu"
            return t

    def get_batch(self, split: str, batch_size: int, block_size: int,
                  generator: torch.Generator | None = None):
        """One vectorised gather, on whichever device the corpus lives on.

        Pass `generator` to draw from a dedicated RNG stream rather than the
        global one, so that evaluating cannot perturb the training sequence.
        """
        d = self.train if split == "train" else self.val
        hi = len(d) - block_size
        if hi < 1:
            raise ValueError(
                f"{split} split holds {len(d)} tokens but block_size is "
                f"{block_size}. Use a bigger corpus or a smaller context window.")
        ix = torch.randint(hi, (batch_size,), device=d.device, generator=generator)
        window = ix[:, None] + torch.arange(block_size + 1, device=d.device)
        chunk = d[window].long()
        # .contiguous(): these are strided views of one gather, and the loss
        # reshapes targets with .view(), which rejects a non-contiguous tensor.
        x, y = chunk[:, :-1].contiguous(), chunk[:, 1:].contiguous()
        if x.device.type != self.device:
            x, y = x.to(self.device), y.to(self.device)
        return x, y
