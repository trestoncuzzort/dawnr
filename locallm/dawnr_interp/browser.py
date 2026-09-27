"""browser.py -- render a sparse autoencoder's dictionary as a markdown feature browser.

Cunningham et al. (arXiv:2309.08600, section 3, see sae.py's docstring for the full
citation) interpret a dictionary feature by looking at the text where it fires most
strongly, then either asking a human or an autointerpretability model (Bills et al.,
2023, which they use) to describe it. This module does the first half -- the top
activating contexts per feature, as markdown a person can read -- and stops there:
no model is asked to name the features, so nothing here claims to know what a feature
"means", only where it fires.
"""
from __future__ import annotations

import torch

from .activations import CachedActivations


def top_contexts(cached: CachedActivations, code: torch.Tensor, feature: int,
                 k: int = 8) -> list[tuple[float, str]]:
    """The up-to-k contexts where dictionary `feature` activates most strongly,
    highest first, paired with that activation value. `code` is the (n, d_hidden)
    matrix SparseAutoencoder.encode produced from `cached.activations`, so row i of
    `code` and `cached.contexts[i]` describe the same cached position."""
    if code.size(0) != len(cached):
        raise ValueError(f"code has {code.size(0)} rows but cached holds {len(cached)}")
    if not 0 <= feature < code.size(1):
        raise ValueError(f"feature must be in [0, {code.size(1)}); got {feature}")
    column = code[:, feature]
    k = min(k, column.numel())
    top = torch.topk(column, k)
    return [(float(top.values[i]), cached.contexts[int(top.indices[i])]) for i in range(k)]


def feature_stats(code: torch.Tensor, feature: int) -> dict:
    """fires: how many cached rows had this feature active at all; max: its
    strongest activation on this cache (0.0 if it never fired)."""
    column = code[:, feature]
    fires = int((column > 0).sum())
    return {"fires": fires, "total": column.numel(), "max": float(column.max()) if fires else 0.0}


def feature_browser_markdown(cached: CachedActivations, code: torch.Tensor, *,
                             features: list[int] | None = None, top_k: int = 8,
                             title: str = "Feature browser") -> str:
    """One markdown section per feature in `features` (default: every dictionary
    feature -- for a wide dictionary that belongs in a file, which is the point):
    its firing rate and top activating contexts, the token that fired wrapped
    `<<like this>>` (activations.cache_residual_stream's own formatting, kept as-is
    so a context copied out of this file still shows exactly where it fired).

    A feature that never fired on this cache gets a one-line "dead" note instead of
    an empty context list -- silence would look like the section was cut off, not
    like a measurement (sae.dead_features finds the same set numerically for a
    training loop; this is that same fact, written for a reader instead).
    """
    if code.size(0) != len(cached):
        raise ValueError(f"code has {code.size(0)} rows but cached holds {len(cached)}")
    chosen = range(code.size(1)) if features is None else features
    n = code.size(0)
    lines = [f"# {title}", "", f"{n} cached positions, layer {cached.layer}, {code.size(1)} dictionary features.", ""]
    for feature in chosen:
        stats = feature_stats(code, feature)
        lines.append(f"## Feature {feature}")
        lines.append("")
        if stats["fires"] == 0:
            lines.append("_dead: never activated on this cache._")
            lines.append("")
            continue
        lines.append(f"fires on {stats['fires']} of {n} cached positions "
                     f"({stats['fires'] / n:.2%}); max activation {stats['max']:.3f}")
        lines.append("")
        for value, context in top_contexts(cached, code, feature, top_k):
            lines.append(f"- `{value:.3f}`  {context}")
        lines.append("")
    return "\n".join(lines)
