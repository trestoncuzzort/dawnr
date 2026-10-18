"""Bind a development-qualified checkpoint or average to its exact release artifact.

Reuses the identity checks from v6-gcp-heldout.sh and v6_compare.py.
Prior art: https://github.com/trestoncuzzort/dawnr/blob/main/t/recipes/v6_export.py
"""
from __future__ import annotations

from v6_export import CONVERTER, MODEL, REVISION

ADAPTERS = {
    400: "af314c4595d8e648b1a219097d5985ba30b5afb420733ae9da600bb967b54583",
    1275: "f82df9d94f4ac702f6035c3f665eeff0a56b82d69a432fc7f1bb5004561d9444",
}
CONFIG = "9c8bb1b245107292a495fde1a14d2323ee70eb985a5bed887a865719e65ac178"


def validate_selection(selected, development):
    assert selected["status"] == "candidate-frozen" and selected["development_complete"] is True
    candidate = selected["candidate"]
    assert candidate in ("final", "average"), "unregistered candidate"
    assert development["panel"] == {
        "name": "development-95", "count": 95,
        "sha256": "f807aec7e6b89e524ded720d9ccfb670c1d504a5a5717966a4b870516701daf7"}
    assert development["same_generation_protocol"] is True and development["same_evaluator"] is True
    assert development["development_gain_without_all_seven_regression"] is True
    a, b = (development["arms"][label] for label in ("v5", candidate))
    assert len(a["confirmed_ids"]["1"]) == 6 and len(a["confirmed_ids"]["7"]) == 3
    assert len(b["confirmed_ids"]["1"]) >= 7 and len(b["confirmed_ids"]["7"]) >= 3
    assert not a["unconfirmed_admissions"] and not b["unconfirmed_admissions"]
    assert not any(values for arm in (a, b) for values in arm["integrity"].values())
    expected = f"student-v6:{selected['candidate_gguf_sha256']}:llama-{CONVERTER}"
    assert b["model_identity"] == expected, "selected model differs from development"
    return candidate


def validate_export(selected, exported, package):
    assert exported["base"] == MODEL and exported["revision"] == REVISION
    assert exported["converter_commit"] == package["converter_commit"] == CONVERTER
    assert exported["quantization"] == "Q8_0"
    source = exported["adapter"]
    if selected["candidate"] == "average":
        assert source["kind"] == "uniform-checkpoint-average" and source["weights"] == [0.5, 0.5]
        components = source["components"]
        assert [part["step"] for part in components] == [1275, 400]
        assert package["adapter_step"] is None
    else:
        assert selected["candidate"] == "final" and source["step"] == package["adapter_step"] == 1275
        components = [source]
    for component in components:
        assert component["files"]["adapter_config.json"] == CONFIG
        assert component["files"]["adapter_model.safetensors"] == ADAPTERS[component["step"]]
    assert selected["adapter"] == package["adapter"] == source
    assert selected["candidate_gguf_sha256"] == exported["output"]["sha256"] == package["source_gguf_sha256"]
    assert selected["candidate_release_manifest_sha256"] == package["manifest_sha256"]
