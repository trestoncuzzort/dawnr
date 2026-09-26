"""Fill-in-the-middle: the decoder-only form of denoising, per document.

Bavarian et al., "Efficient Training of Language Models to Fill in the
Middle" (arXiv:2207.14255), sections 3, 3.1, 4.5 and appendices C and D. With
probability `fim_rate` a document is cut at two character positions drawn
uniformly at random into prefix, middle and suffix, and emitted as

    PSM:  <PRE> prefix <SUF> suffix <MID> middle <EOT>
    SPM:  <PRE> <SUF> suffix <MID> prefix middle <EOT>

with the loss on every token, sentinels and <EOT> included (section 3: "we
keep the loss on all three sections ... it is important to always train on
the <eot> tokens as it signals a successful join to the suffix"). Each part
is encoded separately (appendix C, character_level_psm_fim). The SPM layout is
the paper's second variant (appendix D), chosen there so SPM data also occurs
inside PSM training whenever the prefix is empty; FIM documents are split
between the two modes by `spm_rate`, 0.5 in the paper's main runs.

The two cut points are sorted independent uniform draws over 0..len(doc), the
same draw bigcode's Megatron-LM uses (`np.random.randint(0, len+1, size=2)`,
sorted), which makes each part a third of the document in expectation, as
section 3 states.

Why here: locallm memorises its fine-tune corpus (0.11 nats/token on training
text against 0.68 held out). A document seen left to right teaches one
ordering; transformed afresh every epoch it is a different prediction problem
each time, and the model has to use the suffix to predict the middle.

`span="t"` is this project's addition and is NOT from the paper (section 8.2
lists syntax-aware spans as future work): for a t document the middle is one
whole syntactic unit (a requires/ensures clause, an invariant or decreases
line, or a statement), chosen with probability 0.5, and a character-level span
otherwise, because section 4.5 finds line-only spans fail at random-span
infilling (0.015 against 0.321) and 8.1 recommends always keeping some
character-level spans.
"""
from __future__ import annotations

import random
import re

# Display names only. They are never matched in text: a sentinel id sits past
# the end of the base vocabulary, where no encode() of ordinary text can reach.
PRE, SUF, MID, EOT = "<PRE>", "<SUF>", "<MID>", "<EOT>"
SENTINELS = (PRE, SUF, MID, EOT)
SPANS = ("char", "t")

# A clause or statement line of a t program: the unit a t-aware middle covers.
_CLAUSE = re.compile(r"^(requires|ensures|invariant|decreases)\b")
_STATEMENT = re.compile(r";\s*$")


def has_sentinels(tokenizer) -> bool:
    return tuple(getattr(tokenizer, "sentinels", ())) == SENTINELS


def require_sentinels(tokenizer) -> None:
    if not has_sentinels(tokenizer):
        raise ValueError("FIM needs a tokenizer carrying the FIM sentinels "
                         f"{SENTINELS}; build it with .with_sentinels(fim.SENTINELS)")


def doc_rng(seed: int, epoch: int, index: int) -> random.Random:
    """One generator per (run seed, epoch, document).

    A str seed goes through sha512 in random.seed (version 2), so this is the
    same across processes and PYTHONHASHSEED values, and a resumed run redraws
    exactly the transforms it would have drawn.
    """
    return random.Random(f"fim:{seed}:{epoch}:{index}")


def char_split(doc: str, rng: random.Random) -> tuple[str, str, str]:
    """prefix, middle, suffix at two uniform character positions (section 3, 4.5)."""
    a, b = sorted((rng.randint(0, len(doc)), rng.randint(0, len(doc))))
    return doc[:a], doc[a:b], doc[b:]


def t_units(doc: str) -> list[tuple[int, int]]:
    """Character ranges of the whole clauses and statements in a t document.

    A range runs from the line's first non-blank character to its end, newline
    excluded, so the middle is the unit itself and the indentation stays with
    the prefix.
    """
    units, offset = [], 0
    for line in doc.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        stripped = body.lstrip()
        if stripped and (_CLAUSE.match(stripped) or _STATEMENT.search(stripped)):
            start = offset + len(body) - len(stripped)
            units.append((start, offset + len(body)))
        offset += len(line)
    return units


def t_split(doc: str, rng: random.Random) -> tuple[str, str, str]:
    """A whole unit half the time, a character span otherwise (or when there is no unit)."""
    units = t_units(doc)
    if units and rng.random() < 0.5:
        a, b = units[rng.randrange(len(units))]
        return doc[:a], doc[a:b], doc[b:]
    return char_split(doc, rng)


def split(doc: str, rng: random.Random, span: str = "char") -> tuple[str, str, str]:
    if span == "char":
        return char_split(doc, rng)
    if span == "t":
        return t_split(doc, rng)
    raise ValueError(f"unknown FIM span {span!r}; expected one of {SPANS}")


def encode_fim(tokenizer, prefix: str, middle: str, suffix: str, spm: bool = False) -> list[int]:
    """The token ids of one FIM document, each part encoded on its own (appendix C)."""
    pre, suf, mid, eot = (tokenizer.sentinel_id(s) for s in SENTINELS)
    if spm:
        return ([pre, suf] + tokenizer.encode(suffix) + [mid]
                + tokenizer.encode(prefix) + tokenizer.encode(middle) + [eot])
    return ([pre] + tokenizer.encode(prefix) + [suf] + tokenizer.encode(suffix)
            + [mid] + tokenizer.encode(middle) + [eot])


def transform(doc: str, tokenizer, rng: random.Random, fim_rate: float,
              spm_rate: float = 0.5, span: str = "char") -> list[int] | None:
    """FIM ids for `doc` with probability fim_rate, else None (leave it left to right).

    The draws are made in a fixed order (apply?, mode, cut) so the choice of
    mode never shifts where a document is cut.
    """
    if fim_rate <= 0 or rng.random() >= fim_rate:
        return None
    spm = rng.random() < spm_rate
    prefix, middle, suffix = split(doc, rng, span)
    return encode_fim(tokenizer, prefix, middle, suffix, spm=spm)


def infill_prompt(tokenizer, prefix: str, suffix: str, spm: bool = False) -> list[int]:
    """The inference prompt of section 3 (PSM) or appendix D (SPM); the model writes the middle, then <EOT>."""
    pre, suf, mid, _ = (tokenizer.sentinel_id(s) for s in SENTINELS)
    if spm:
        return [pre, suf] + tokenizer.encode(suffix) + [mid] + tokenizer.encode(prefix)
    return [pre] + tokenizer.encode(prefix) + [suf] + tokenizer.encode(suffix) + [mid]


def infill(model, tokenizer, prefix: str, suffix: str, max_new_tokens: int = 200,
           spm: bool = False) -> tuple[str, bool]:
    """Greedy middle for (prefix, suffix), and whether the model closed it with <EOT>.

    Section 3: a model that does not emit <EOT> within the budget "is having a
    difficult time connecting the prefix and the suffix", so that flag is
    returned rather than hidden.
    """
    import torch

    eot = tokenizer.sentinel_id(EOT)
    device = next(model.parameters()).device
    ids = infill_prompt(tokenizer, prefix, suffix, spm=spm)
    out: list[int] = []
    closed = False
    was_training = model.training
    model.eval()
    try:
        with torch.no_grad():
            for _ in range(max_new_tokens):
                window = (ids + out)[-model.config.block_size:]
                logits, _ = model(torch.tensor([window], device=device), only_last=True)
                nxt = int(logits[0, -1].argmax())
                if nxt == eot:
                    closed = True
                    break
                out.append(nxt)
    finally:
        model.train(was_training)
    return tokenizer.decode(out), closed
