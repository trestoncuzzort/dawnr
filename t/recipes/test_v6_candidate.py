"""Selection cannot exchange model identities, source checkpoints, or development gates."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import v6_candidate as candidate


def fixture():
    source = {"kind": "uniform-checkpoint-average", "weights": [0.5, 0.5], "components": [
        {"step": step, "files": {"adapter_config.json": candidate.CONFIG,
                                "adapter_model.safetensors": candidate.ADAPTERS[step]}}
        for step in (1275, 400)]}
    selected = {"status": "candidate-frozen", "development_complete": True, "candidate": "average",
                "adapter": copy.deepcopy(source), "candidate_gguf_sha256": "model",
                "candidate_release_manifest_sha256": "manifest"}
    development = {"panel": {"name": "development-95", "count": 95,
                             "sha256": "f807aec7e6b89e524ded720d9ccfb670c1d504a5a5717966a4b870516701daf7"},
                   "same_generation_protocol": True, "same_evaluator": True,
                   "development_gain_without_all_seven_regression": True,
                   "arms": {name: {"confirmed_ids": {"1": list(range(n)), "7": [1, 2, 3]},
                                   "unconfirmed_admissions": [], "integrity": {"contradictions": [], "unsound_cells": []},
                                   "model_identity": f"student-v6:model:llama-{candidate.CONVERTER}"}
                            for name, n in (("v5", 6), ("average", 7))}}
    exported = {"base": candidate.MODEL, "revision": candidate.REVISION, "converter_commit": candidate.CONVERTER,
                "quantization": "Q8_0", "adapter": copy.deepcopy(source), "output": {"sha256": "model"}}
    package = {"converter_commit": candidate.CONVERTER, "adapter_step": None, "adapter": copy.deepcopy(source),
               "source_gguf_sha256": "model", "manifest_sha256": "manifest"}
    return selected, development, exported, package


def test_only_the_qualified_development_artifact_and_its_source_checkpoints_can_advance():
    selected, development, exported, package = fixture()
    assert candidate.validate_selection(selected, development) == "average"
    candidate.validate_export(selected, exported, package)


@pytest.mark.parametrize("change", ["model", "tie", "all-seven", "unconfirmed", "unsound", "panel", "protocol"])
def test_an_incomplete_or_different_development_result_refuses_selection(change):
    selected, development, _, _ = fixture()
    arm = development["arms"]["average"]
    if change == "model": selected["candidate_gguf_sha256"] = "other"
    elif change == "tie": arm["confirmed_ids"]["1"].pop()
    elif change == "all-seven": arm["confirmed_ids"]["7"].pop()
    elif change == "unconfirmed": arm["unconfirmed_admissions"] = [1]
    elif change == "unsound": arm["integrity"]["unsound_cells"] = [["task", "kernel"]]
    elif change == "panel": development["panel"]["sha256"] = "other"
    else: development["same_generation_protocol"] = False
    with pytest.raises(AssertionError):
        candidate.validate_selection(selected, development)


@pytest.mark.parametrize("change", ["weights", "component", "base", "package", "manifest"])
def test_export_cannot_replace_the_registered_average(change):
    selected, _, exported, package = fixture()
    if change == "weights": exported["adapter"]["weights"] = [0.25, 0.75]
    elif change == "component": exported["adapter"]["components"][0]["files"]["adapter_model.safetensors"] = "other"
    elif change == "base": exported["revision"] = "other"
    elif change == "package": package["adapter"] = {}
    else: package["manifest_sha256"] = "other"
    with pytest.raises(AssertionError):
        candidate.validate_export(selected, exported, package)
