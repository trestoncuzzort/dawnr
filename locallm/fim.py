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

`span="t"` follows AST-FIM (Gong et al., "Structure-Aware Fill-in-the-Middle
Pretraining for Code", arXiv:2506.00204, section 3.3 and 5.1), which the
paper above lists as future work in its 8.2: the middle is one whole
syntactic unit, sampled with probability proportional to its size in
characters (AST-FIM's single-node masking), for 90% of FIM documents, and a
random character span for the other 10% (AST-FIM's mix; its section 7 finds
that without the random share the model fails at random-span infilling, as
Bavarian et al. 4.5 found for line spans). t's units, in AST-FIM's taxonomy
of blocks, statements and expressions: a clause (requires/ensures), an
invariant (invariant/decreases), a statement (a line ending in `;`), an
expression (a clause's condition, a loop or branch condition, the right side
of `:=`), and a block (a `{ ... }` region, braces included). Units are found
lexically, not by t's parser, so this module stays free of the t package;
AST-FIM's aligned-span masking (several adjacent siblings) is not
implemented.
"""
from __future__ import annotations

import random
import re

# Display names only. They are never matched in text: a sentinel id sits past
# the end of the base vocabulary, where no encode() of ordinary text can reach.
PRE, SUF, MID, EOT = "<PRE>", "<SUF>", "<MID>", "<EOT>"
SENTINELS = (PRE, SUF, MID, EOT)
SPANS = ("char", "t")

# The syntactic units of a t program a t-aware middle covers (see t_units).
_CLAUSE = re.compile(r"^(requires|ensures)\s+(.+?)\s*$")
_INVARIANT = re.compile(r"^(invariant|decreases)\s+(.+?)\s*$")
_CONDITION = re.compile(r"^(?:\}\s*else\s+)?(?:while|if)\s+(.+?)\s*\{?\s*$")
_ASSIGN = re.compile(r":=\s*(.+?)\s*;\s*$")
_STATEMENT = re.compile(r";\s*$")
T_UNIT_KINDS = ("clause", "invariant", "statement", "expression", "block")
T_SYNTAX_SHARE = 0.9   # AST-FIM section 5.1: 90% AST-FIM, 10% random-character FIM


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


def t_units(doc: str) -> list[tuple[int, int, str]]:
    """(start, end, kind) of every syntactic unit of a t document.

    A line unit runs from the line's first non-blank character to its end,
    newline excluded, so the indentation stays with the prefix. An expression
    is the text after its keyword or `:=`, without the `;` or `{`. A block runs
    from a `{` to its matching `}`.
    """
    units, offset, opens = [], 0, []
    for line in doc.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        stripped = body.lstrip()
        start = offset + len(body) - len(stripped)
        end = offset + len(body)
        if stripped:
            for pattern, kind in ((_CLAUSE, "clause"), (_INVARIANT, "invariant")):
                m = pattern.match(stripped)
                if m:
                    units.append((start, end, kind))
                    units.append((start + m.start(2), start + m.end(2), "expression"))
            m = _CONDITION.match(stripped)
            if m:
                units.append((start + m.start(1), start + m.end(1), "expression"))
            if _STATEMENT.search(stripped) and not _CLAUSE.match(stripped):
                units.append((start, end, "statement"))
                m = _ASSIGN.search(stripped)
                if m:
                    units.append((start + m.start(1), start + m.end(1), "expression"))
        for k, ch in enumerate(line):
            if ch == "{":
                opens.append(offset + k)
            elif ch == "}" and opens:
                units.append((opens.pop(), offset + k + 1, "block"))
        offset += len(line)
    return [u for u in units if u[1] > u[0]]


def t_split(doc: str, rng: random.Random) -> tuple[str, str, str]:
    """One whole unit, size-weighted, for 90% of documents; a character span otherwise.

    The size weighting is AST-FIM's single-node masking ("probability
    proportional to its size"); a document with no unit falls back to a
    character span."""
    units = t_units(doc)
    if units and rng.random() < T_SYNTAX_SHARE:
        a, b, _ = rng.choices(units, weights=[b - a for a, b, _ in units])[0]
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
