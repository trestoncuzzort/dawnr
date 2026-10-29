"""The current release cannot select on a mean, incomplete evidence, or a second seed trial."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent / "recipes"))
import release_seed_selection as choose


def development(registration, ids, counts=None):
    counts = counts or {1: (30, 10), 2: (30, 10)}
    names = (registration["baseline_name"], registration["candidate_name"])
    readings = {}
    for level, column in (("clean", 0), ("all_seven", 1)):
        base = [(tag, set(ids[:20 if column == 0 else 8])) for tag in registration["baseline_tags"]]
        candidate = [(tag, set(ids[:counts[s][column]])) for s in (1, 2)
                     for tag in choose.tags_for(registration["seeds"][str(s)]["prefix"])]
        readings[level] = {name: choose.report_tool.model_reading(name, pairs, ids)
                           for name, pairs in zip(names, (base, candidate))}
    result = {"panel": "registered-clean-panel.txt", "problems": 206,
              "protocol": "paired per-problem fractions over the decode sets", "decodes": {names[0]: 3, names[1]: 6},
              "expected_decodes": {names[0]: 3, names[1]: 6}, "unequal_decodes": True, "readings": readings,
              "paired": {level: choose.report_tool.compare(r[names[0]], r[names[1]], ids) for level, r in readings.items()}}
    return json.loads(json.dumps(result))  # Exercise the same string-key round trip as saved reports.


def bindings(registration, report, seeds):
    bound = {"registration": choose.sha(registration), "development_report": choose.sha(report), "development_audit": "a" * 64}
    for seed, data in seeds.items():
        for field in ("export", "precision", "precision_receipt", "spec33_receipt", "generation_audit"):
            bound[f"seed_{seed}_{field}"] = choose.sha(data[field])
    return bound


@pytest.fixture
def evidence():
    ids = list(range(206))
    reg = {"candidate": "fixture", "training_rows_sha256": "e" * 64, "steps_per_seed": 2160,
           "development_panel_sha256": hashlib.sha256("".join(str(i) + "\n" for i in ids).encode()).hexdigest(),
           "heldout_panel_sha256": "9" * 64,
           "baseline_name": "released", "candidate_name": "candidate", "baseline_tags": ["base0", "base1000", "base2000"],
           "seeds": {str(s): {"prefix": f"fixture-s{s}", "export_name": f"fixture-export-{s}"} for s in (1, 2)},
           "precision_sources": {"t/spec_check.py": "a" * 64, "t/recipes/spec_ceiling.py": "b" * 64},
           "spec33_sources": {"t/score_spec_given.py": "c" * 64, "t/recipes/grade_spec33.py": "d" * 64}}
    seeds = {}
    for s in (1, 2):
        prefix = reg["seeds"][str(s)]["prefix"]; model = str(s) * 64
        export = {"base": choose.MODEL, "revision": choose.REVISION, "converter_commit": choose.CONVERTER,
                  "quantization": "Q8_0", "merge_dtype": "bfloat16", "name": reg["seeds"][str(s)]["export_name"],
                  "adapter": {"kind": "cohere-curated-sft", "step": 2160, "seed": s,
                              "data_sha256": reg["training_rows_sha256"], "prepared_sha256": "f" * 64,
                              "files": {name: "f" * 64 for name in ("adapter_config.json", "adapter_model.safetensors", "prepared.json", "run.json")}},
                  "output": {"filename": "model-Q8_0.gguf", "bytes": 4096, "sha256": model}}
        manifest = {"tag": prefix + "-spec20", "files": {"spec_first.json": "f" * 64}}
        precision = {"tag": prefix + "-spec20", "draws": 200, "problems": 95,
                     "candidates_scored": 100, "safe_kept": 100,
                     "safe_kept_reference_correct": 70, "safe_precision": .7}
        precision_receipt = {"grader_commit": "01c94ef5509fc51ab6484c1350c1cb9f8504e459",
                             "procedure": {"pool": "v5", "draws": 200, "per_problem": 3, "jobs": 4},
                             "source_sha256": reg["precision_sources"], "input_manifest": manifest, "input_asset_sha256": "a" * 64}
        spec33 = {"label": prefix, "answer_model": prefix,
                  "questions": {"sha256": choose.QUESTIONS_SHA}, "answers": {"sha256": "b" * 64},
                  "input_manifest_sha256": "c" * 64, "code_sha256": reg["spec33_sources"],
                  "levels": {"questions": 33, "ready": 33, "stages": {"ready": 33}, "no row in the table": 0, "proved by at least 1": 29,
                             "proved by at least 3": 29, "proved by at least 5": 28, "proved by at least 6": 28, "proved by all seven": 27},
                  "passes_spec33_requirement": True}
        generation = {"development_models": {choose.tag_for(prefix, p, offset): model
                      for p in ("dev-95", "wider-145") for offset in choose.OFFSETS},
                      "precision_model_sha256": model, "precision_input_asset_sha256": "a" * 64,
                      "spec33_model_sha256": model, "spec33_identity_sha256": "d" * 64,
                      "precision_input_manifest": manifest, "spec33_answers_sha256": "b" * 64,
                      "spec33_input_manifest_sha256": "c" * 64}
        seeds[s] = {"export": export, "precision": precision, "precision_receipt": precision_receipt,
                    "spec33_receipt": spec33, "generation_audit": generation}
    return reg, development(reg, ids), ids, seeds


def decide(evidence):
    reg, report, ids, seeds = evidence
    return choose.decide(reg, report, ids, seeds, bindings(reg, report, seeds))


def test_complete_paired_result_and_exact_boundary_qualify(evidence):
    result = decide(evidence)
    assert result["status"] == "eligible-for-heldout" and result["selected_seed"] == 1
    assert result["seeds"]["1"]["precision"] == .7 and not result["heldout_started"]


@pytest.mark.parametrize("counts,winner", [({1: (30, 10), 2: (31, 10)}, 2),
                                           ({1: (30, 10), 2: (30, 11)}, 2),
                                           ({1: (30, 10), 2: (30, 10)}, 1)])
def test_registered_tie_break_order(evidence, counts, winner):
    reg, _, ids, seeds = evidence
    assert decide((reg, development(reg, ids, counts), ids, seeds))["selected_seed"] == winner


def test_better_mean_does_not_replace_the_paired_gate(evidence):
    reg, _, ids, seeds = evidence
    result = decide((reg, development(reg, ids, {1: (21, 10), 2: (21, 10)}), ids, seeds))
    assert not result["development_passed"] and result["selected_seed"] is None


def test_best_development_seed_must_pass_both_individual_gates(evidence):
    reg, _, ids, seeds = evidence
    seeds[2]["precision"].update(safe_kept_reference_correct=69, safe_precision=.69)
    result = decide((reg, development(reg, ids, {1: (30, 10), 2: (40, 20)}), ids, seeds))
    assert result["selected_seed"] == 1 and result["eligible_seeds"] == [1]
    seeds[1]["spec33_receipt"]["levels"]["proved by all seven"] = 26
    seeds[1]["spec33_receipt"]["passes_spec33_requirement"] = False
    assert decide((reg, development(reg, ids), ids, seeds))["selected_seed"] is None


def test_zero_precision_denominator_is_a_valid_failed_measurement(evidence):
    evidence[3][1]["precision"].update(safe_kept=0, safe_kept_reference_correct=0, safe_precision=None)
    assert decide(evidence)["selected_seed"] == 2


def test_precision_counts_all_kept_samples_before_the_top_three_cap(evidence):
    # spec_ceiling measures every "kept" record; per_problem=3 caps only its
    # selection-gap ranking. Four kept samples on 75 problems is valid.
    evidence[3][1]["precision"].update(candidates_scored=400, safe_kept=300,
                                      safe_kept_reference_correct=210, safe_precision=.7)
    assert decide(evidence)["seeds"]["1"]["precision_passed"]


@pytest.mark.parametrize("scored,kept", [(100, 101), (1901, 100), (-1, 0), (True, 1)])
def test_precision_counts_cannot_exceed_the_registered_twenty_samples(evidence, scored, kept):
    evidence[3][1]["precision"].update(candidates_scored=scored, safe_kept=kept,
                                      safe_kept_reference_correct=0, safe_precision=0 if kept else None)
    with pytest.raises(ValueError, match="precision counts"):
        decide(evidence)


@pytest.mark.parametrize("field", ["mean", "fraction", "p", "missing", "foreign", "repeat"])
def test_changed_or_incomplete_development_report_is_refused(evidence, field):
    report = evidence[1]; candidate = report["readings"]["clean"]["candidate"]
    if field == "mean": candidate["mean"] += 1
    elif field == "fraction": candidate["fraction"]["0"] = .5
    elif field == "p": report["paired"]["clean"]["permutation_test"]["p"] = 0
    elif field == "missing": candidate["decodes"].pop()
    elif field == "foreign": candidate["decodes"][0]["ids"][0] = 999999
    else: candidate["decodes"][-1] = deepcopy(candidate["decodes"][0])
    with pytest.raises(ValueError): decide(evidence)


@pytest.mark.parametrize("change", ["model", "spec-model", "spec-identity", "part", "checkpoint", "dataset", "precision-source", "spec-source", "spec-panel", "missing-cell", "precision-ratio", "precision-nan"])
def test_unmatched_or_malformed_seed_evidence_is_refused(evidence, change):
    data = evidence[3][1]
    if change == "model": data["generation_audit"]["precision_model_sha256"] = "2" * 64
    elif change == "spec-model": data["generation_audit"]["spec33_model_sha256"] = "2" * 64
    elif change == "spec-identity": data["generation_audit"]["spec33_identity_sha256"] = "label-only"
    elif change == "part": data["generation_audit"]["development_models"].popitem()
    elif change == "checkpoint": data["export"]["adapter"]["step"] = 100
    elif change == "dataset": data["export"]["adapter"]["data_sha256"] = "d" * 64
    elif change == "precision-source": data["precision_receipt"]["source_sha256"] = {}
    elif change == "spec-source": data["spec33_receipt"]["code_sha256"] = {}
    elif change == "spec-panel": data["spec33_receipt"]["questions"]["sha256"] = "d" * 64
    elif change == "missing-cell": data["spec33_receipt"]["levels"]["no row in the table"] = 1
    elif change == "precision-ratio": data["precision"]["safe_precision"] = .71
    else: data["precision"]["safe_precision"] = float("nan")
    with pytest.raises(ValueError): decide(evidence)


def test_bindings_must_cover_all_inputs_and_match_their_contents(evidence):
    reg, report, ids, seeds = evidence; hashes = bindings(reg, report, seeds)
    hashes["seed_1_precision"] = "0" * 64
    with pytest.raises(ValueError, match="binding"):
        choose.decide(reg, report, ids, seeds, hashes)
    hashes = bindings(reg, report, seeds); hashes.pop("development_audit")
    with pytest.raises(ValueError, match="evidence bindings"):
        choose.decide(reg, report, ids, seeds, hashes)


def test_heldout_choice_cannot_switch_seed_or_rewrite_evidence(evidence, tmp_path):
    reg, report, ids, seeds = evidence; path = tmp_path / "choice.json"
    hashes = bindings(reg, report, seeds)
    first = choose.freeze_heldout_choice(path, reg, report, ids, seeds, hashes)
    assert choose.freeze_heldout_choice(path, reg, report, ids, seeds, hashes) == first
    changed = development(reg, ids, {1: (30, 10), 2: (31, 10)})
    with pytest.raises(ValueError, match="already frozen"):
        choose.freeze_heldout_choice(path, reg, changed, ids, seeds, bindings(reg, changed, seeds))
    assert json.loads(path.read_text()) == first


def test_unqualified_candidate_creates_no_heldout_choice(evidence, tmp_path):
    reg, _, ids, seeds = evidence; report = development(reg, ids, {1: (20, 8), 2: (20, 8)})
    path = tmp_path / "choice.json"
    with pytest.raises(ValueError, match="not qualified"):
        choose.freeze_heldout_choice(path, reg, report, ids, seeds, bindings(reg, report, seeds))
    assert not path.exists()


def test_another_206_problem_panel_is_refused(evidence):
    reg, report, ids, seeds = evidence
    altered = ids[:-1] + [999999]
    with pytest.raises(ValueError, match="panel changed"):
        choose.decide(reg, report, altered, seeds, bindings(reg, report, seeds))
