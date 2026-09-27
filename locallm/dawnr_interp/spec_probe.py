"""spec_probe.py -- the first question AMBITION.md asks of this dictionary: do any
features fire on specifications and loop invariants, as opposed to memorised
boilerplate?

"Specification" is operationalised as a line carrying one of t's own clause
keywords -- `requires`, `ensures`, `invariant`, `decreases` (t/surface.py's Clause
production), or `spec` (which opens a specification-only helper function). This is
what a person writing a t program the reader called "the specification" or "the
invariant" typed, not a guess at what a neuron might mean.

"Boilerplate" is operationalised as a line whose stripped text repeats near-
verbatim across many documents (`i := i + 1;`, a lone `{`) -- the surface idiom
every task restates, the closest measurable proxy this module has for "memorised
structure" without needing a second model to judge memorisation. It is a proxy, not
a definition of memorisation, and the report says so.

Everything here is a statistic over one cache, not a claim about the model overall
(AGENTS.md rule 1): render_report's own text repeats that on purpose so it survives
being read on its own.
"""
from __future__ import annotations

import bisect
import re
from collections import Counter
from dataclasses import dataclass

import torch

from . import browser
from .activations import CachedActivations

# t/surface.py KEYWORDS has the full grammar; these five are its Clause production
# plus `spec` (t/surface.py:121-133 and the "spec fun" declarations in t/tasks/*.t),
# i.e. the keywords that only ever appear when stating what a program assumes or
# must guarantee. Structural keywords (`task`, `var`, `if`, `while`, ...) are
# deliberately excluded: they shape control flow, they do not specify anything.
SPEC_KEYWORDS = ("requires", "ensures", "invariant", "decreases", "spec")
_SPEC_WORD = re.compile(r"\b(?:" + "|".join(SPEC_KEYWORDS) + r")\b")


def label_lines(document: str, *, boilerplate_lines: frozenset[str] = frozenset()) -> list[str]:
    """One label per line of `document`, in order: "spec" first (a keyword line is
    always a spec line even if its exact text also repeats elsewhere -- `decreases
    n` is still a specification the hundredth time it is written), then
    "boilerplate" (the stripped line is in `boilerplate_lines`), else "other"."""
    labels = []
    for line in document.split("\n"):
        if _SPEC_WORD.search(line):
            labels.append("spec")
        elif line.strip() and line.strip() in boilerplate_lines:
            labels.append("boilerplate")
        else:
            labels.append("other")
    return labels


def boilerplate_lines(documents: list[str], *, min_documents: int = 8,
                      min_fraction: float = 0.02) -> frozenset[str]:
    """Stripped lines that recur across at least `threshold` documents, where
    threshold = max(2, min(min_documents, round(min_fraction * len(documents)))):
    never more than `min_documents` occurrences even on a huge corpus (a flat
    absolute cap, so requiring a fixed share of a huge corpus can never demand an
    unreasonable count), never fewer than 2 (a single coincidental repeat is not
    yet a pattern) even on a tiny one, and scaled down toward `min_fraction`'s
    share of the corpus whenever that share is smaller than `min_documents`. A
    line counts once per document it appears in, never once per occurrence, so a
    line repeated many times inside a single loop cannot inflate its own count.
    """
    if not documents:
        return frozenset()
    if not 0 <= min_fraction <= 1:
        raise ValueError("min_fraction must be within [0, 1]")
    if min_documents < 1:
        raise ValueError("min_documents must be positive")
    counts: Counter = Counter()
    for doc in documents:
        for stripped in {ln.strip() for ln in doc.split("\n") if ln.strip()}:
            counts[stripped] += 1
    threshold = max(2, min(min_documents, round(min_fraction * len(documents))))
    return frozenset(line for line, n in counts.items() if n >= threshold)


def _line_starts(document: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(document):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _char_offsets(tok, ids: list[int]) -> list[int]:
    """Character offset where each token's decoded text begins, found by
    accumulating single-token decode lengths. Exact for a one-character-per-token
    tokenizer (CharTokenizer -- every checkpoint in this repository today); an
    approximation under byte-level BPE if a multi-byte character is split across
    two tokens, the same edge case sample()'s docstring in checkpoint.py already
    names (a token decoded alone can end in U+FFFD where decoding it with its
    neighbour would not) -- rare in source text, and it can only misattribute a
    position to the line beside the right one, never further."""
    offsets = []
    cursor = 0
    for tid in ids:
        offsets.append(cursor)
        cursor += len(tok.decode([tid]))
    return offsets


def token_line_labels(document: str, tok, *, boilerplate_lines: frozenset[str] = frozenset()) -> list[str]:
    """One label per token of tok.encode(document), same order activations.py's
    cache_residual_stream records `position` in, so labels[position] is that
    token's line's label."""
    ids = tok.encode(document)
    if not ids:
        return []
    labels_by_line = label_lines(document, boilerplate_lines=boilerplate_lines)
    starts = _line_starts(document)
    labels = []
    for offset in _char_offsets(tok, ids):
        line = bisect.bisect_right(starts, offset) - 1
        line = min(max(line, 0), len(labels_by_line) - 1)
        labels.append(labels_by_line[line])
    return labels


def label_cached_activations(cached: CachedActivations, documents: list[str], tok, *,
                             boilerplate_lines: frozenset[str] = frozenset()) -> list[str]:
    """Same length and order as cached.activations: the spec/boilerplate/other
    label of the source line each cached row's token came from."""
    per_document: dict[int, list[str]] = {}
    labels = []
    for doc_i, position in zip(cached.doc_index, cached.position):
        if doc_i not in per_document:
            per_document[doc_i] = token_line_labels(documents[doc_i], tok, boilerplate_lines=boilerplate_lines)
        labels.append(per_document[doc_i][position])
    return labels


@dataclass
class FeatureContrast:
    feature: int
    spec_mean: float
    boilerplate_mean: float
    other_mean: float
    spec_rate: float           # fraction of spec-labeled rows where this feature fired at all
    boilerplate_rate: float
    contrast: float            # (spec_mean - boilerplate_mean) / this feature's own activation std


def feature_label_contrast(code: torch.Tensor, labels: list[str]) -> list[FeatureContrast]:
    """For every dictionary feature (a column of `code`, an (n, d_hidden) SAE code
    matrix), contrast its activation on "spec"-labeled rows against
    "boilerplate"-labeled ones. `contrast` is in units of the feature's own
    activation standard deviation (a plain mean difference is not comparable across
    features whose activations sit at very different scales); a feature missing
    either label entirely gets contrast 0.0 rather than an undefined or infinite
    value, so an unlucky small sample cannot masquerade as the strongest result.
    """
    if code.size(0) != len(labels):
        raise ValueError(f"code has {code.size(0)} rows but got {len(labels)} labels")
    spec_mask = torch.tensor([label == "spec" for label in labels])
    boiler_mask = torch.tensor([label == "boilerplate" for label in labels])
    other_mask = ~spec_mask & ~boiler_mask
    overall_std = code.std(dim=0).clamp_min(1e-8)
    results = []
    for feature in range(code.size(1)):
        column = code[:, feature]
        spec_vals, boiler_vals, other_vals = column[spec_mask], column[boiler_mask], column[other_mask]
        spec_mean = float(spec_vals.mean()) if spec_vals.numel() else 0.0
        boiler_mean = float(boiler_vals.mean()) if boiler_vals.numel() else 0.0
        contrast = (spec_mean - boiler_mean) / float(overall_std[feature]) \
            if spec_vals.numel() and boiler_vals.numel() else 0.0
        results.append(FeatureContrast(
            feature=feature, spec_mean=spec_mean, boilerplate_mean=boiler_mean,
            other_mean=float(other_vals.mean()) if other_vals.numel() else 0.0,
            spec_rate=float((spec_vals > 0).float().mean()) if spec_vals.numel() else 0.0,
            boilerplate_rate=float((boiler_vals > 0).float().mean()) if boiler_vals.numel() else 0.0,
            contrast=contrast))
    return results


def _table(rows: list[FeatureContrast]) -> list[str]:
    out = ["| feature | contrast | spec mean | boilerplate mean | spec fire rate | boilerplate fire rate |",
          "|---|---|---|---|---|---|"]
    for c in rows:
        out.append(f"| {c.feature} | {c.contrast:.2f} | {c.spec_mean:.3f} | {c.boilerplate_mean:.3f} | "
                   f"{c.spec_rate:.1%} | {c.boilerplate_rate:.1%} |")
    return out


def render_report(contrasts: list[FeatureContrast], cached: CachedActivations, code: torch.Tensor, *,
                  top_k_features: int = 10, contexts_per_feature: int = 5,
                  title: str = "Specification vs. boilerplate probe") -> str:
    """Markdown: how many features lean toward specification lines, how many
    toward boilerplate, the top of each ranked list as a table, and a few of each
    list's example contexts pulled from the feature browser. `contrast` beyond
    +/-1.0 (one standard deviation of that feature's own activation) is the only
    threshold used, and it is named here rather than hidden in a filter."""
    if not contrasts:
        raise ValueError("no features to report on")
    if code.size(0) != len(cached):
        raise ValueError("code must have one row per cached activation")
    spec_leaning = sorted(contrasts, key=lambda c: c.contrast, reverse=True)[:top_k_features]
    boilerplate_leaning = sorted(contrasts, key=lambda c: c.contrast)[:top_k_features]
    n_spec_leaning = sum(1 for c in contrasts if c.contrast > 1.0)
    n_boilerplate_leaning = sum(1 for c in contrasts if c.contrast < -1.0)

    lines = [f"# {title}", "",
            f"{len(contrasts)} dictionary features measured on {len(cached)} cached positions "
            f"(layer {cached.layer}). {n_spec_leaning} fire more than one standard deviation harder on "
            f"specification lines (`{'`, `'.join(SPEC_KEYWORDS)}`) than on repeated boilerplate lines; "
            f"{n_boilerplate_leaning} show the opposite pattern. This is a measurement of one cache from "
            "one checkpoint, not a claim about the model in general (AGENTS.md rule 1) -- it says whether "
            "this dictionary drew the two apart today, not that it always will.", ""]

    lines.append("## Most specification-leaning features")
    lines.append("")
    lines += _table(spec_leaning)
    lines.append("")
    for c in spec_leaning[:3]:
        lines.append(f"### Feature {c.feature} (contrast {c.contrast:.2f})")
        lines.append("")
        for value, context in browser.top_contexts(cached, code, c.feature, contexts_per_feature):
            lines.append(f"- `{value:.3f}`  {context}")
        lines.append("")

    lines.append("## Most boilerplate-leaning features")
    lines.append("")
    lines += _table(boilerplate_leaning)
    lines.append("")
    for c in boilerplate_leaning[:3]:
        lines.append(f"### Feature {c.feature} (contrast {c.contrast:.2f})")
        lines.append("")
        for value, context in browser.top_contexts(cached, code, c.feature, contexts_per_feature):
            lines.append(f"- `{value:.3f}`  {context}")
        lines.append("")

    return "\n".join(lines)
