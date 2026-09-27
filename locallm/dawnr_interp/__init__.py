"""dawnr_interp: sparse-autoencoder interpretability for locallm's core (AMBITION.md,
"to be understood from inside").

A dictionary is trained on one residual-stream layer's activations, read only from
the training split of a corpus (activations.training_split_documents); the result is
readable two ways: browser.feature_browser_markdown lists every feature's top
activating contexts, and spec_probe answers a first, narrower question -- whether any
features separate t's own specification keywords (requires/ensures/invariant/
decreases/spec) from repeated boilerplate lines. See README.md for the recipe this
follows and its citation, and run_sae.py for the end-to-end command line.
"""
from .activations import CachedActivations, cache_residual_stream, training_split_documents  # noqa: F401
from .browser import feature_browser_markdown, top_contexts  # noqa: F401
from .sae import SAEConfig, SparseAutoencoder, dead_features, train_sae  # noqa: F401
from .spec_probe import (FeatureContrast, boilerplate_lines, feature_label_contrast,  # noqa: F401
                         label_cached_activations, render_report)
