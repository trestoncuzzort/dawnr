"""Apply the registered two-seed release gates to independently audited evidence.

Artifact recovery, source/evaluator checks and full-panel grading validation must
precede this module. It recomputes the reported statistics, binds every measured
model to its final export, and freezes one choice for the held-out step. It neither
reads held-out answers nor launches generation, grading or publication.

Sources: three_decode_report.py; v6_candidate.py; spec_ceiling.py;
PREDICT-2026-10-29-cohere-curated-candidate.md and RELEASE-6.0-PLAN.md section 3.
https://github.com/trestoncuzzort/dawnr/blob/main/t/recipes/three_decode_report.py
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

import three_decode_report as report_tool
from release_decode_arms import tag_for
from release_grading_inputs import QUESTIONS_SHA
from v6_export import MODEL, REVISION, CONVERTER

HEX = re.compile(r"[0-9a-f]{64}")
SEEDS = (1, 2)
OFFSETS = (0, 1000, 2000)


def require(value, reason):
    if not value:
        raise ValueError(reason)


def canonical(value):
    # Reports use integer problem keys in memory and string keys after JSON loading.
    def normalize(item):
        if isinstance(item, dict):
            require(all(type(k) in (str, int) for k in item), "invalid evidence object key")
            result = {str(k): normalize(v) for k, v in item.items()}
            require(len(result) == len(item), "duplicate normalized evidence key")
            return result
        if isinstance(item, (list, tuple)):
            return [normalize(v) for v in item]
        return item
    return json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def integer(value, low=0, high=None):
    return type(value) is int and value >= low and (high is None or value <= high)


def check_digest(value, reason="invalid evidence digest"):
    require(isinstance(value, str) and HEX.fullmatch(value), reason)
    return value


def tags_for(prefix):
    return [tag_for(prefix, "dev-95", offset) for offset in OFFSETS]


def validate_development(report, ids, baseline_name, candidate_name, baseline_tags, seed_prefixes):
    """Recompute every reading and paired statistic from the complete decode sets."""
    require(len(ids) == len(set(ids)) == 206 and all(integer(i) for i in ids), "expected the complete clean 206 panel")
    require(set(seed_prefixes) == set(SEEDS), "both registered training seeds are required")
    candidate_tags = [tag for seed in SEEDS for tag in tags_for(seed_prefixes[seed])]
    require(len(baseline_tags) == len(set(baseline_tags)) == 3
            and len(set(candidate_tags)) == 6 and not set(baseline_tags) & set(candidate_tags), "decode tags are incomplete or repeated")
    names = (baseline_name, candidate_name)
    require(len(set(names)) == 2, "baseline and candidate names must differ")
    expected_counts = {baseline_name: 3, candidate_name: 6}
    require(report["problems"] == 206 and report["decodes"] == expected_counts
            and report["expected_decodes"] == expected_counts and report["unequal_decodes"] is True, "the declared three-versus-six protocol changed")
    require(report["protocol"] == "paired per-problem fractions over the decode sets", "different comparison protocol")
    readings, sets = {}, {}
    for level in ("clean", "all_seven"):
        require(set(report["readings"][level]) == set(names), "foreign model in development report")
        readings[level], sets[level] = {}, {}
        for model, expected in ((baseline_name, baseline_tags), (candidate_name, candidate_tags)):
            saved = report["readings"][level][model]
            decoded = saved["decodes"]
            require(len(decoded) == len(expected) and {d["tag"] for d in decoded} == set(expected), "missing or duplicate decode")
            pairs = []
            for decode in decoded:
                members = decode["ids"]
                require(all(integer(i) for i in members) and len(members) == len(set(members))
                        and set(members) <= set(ids) and decode["count"] == len(members), "foreign or duplicate solved problem")
                pairs.append((decode["tag"], set(members)))
            rebuilt = report_tool.model_reading(model, pairs, ids)
            require(canonical(saved) == canonical(rebuilt), "development totals or fractions differ from decode sets")
            readings[level][model] = rebuilt
            sets[level][model] = dict(pairs)
        paired = report_tool.compare(readings[level][baseline_name], readings[level][candidate_name], ids)
        require(canonical(report["paired"][level]) == canonical(paired), "paired statistics differ from decode sets")
    for model in names:
        require(all(values <= sets["clean"][model][tag] for tag, values in sets["all_seven"][model].items()), "all-seven set exceeds clean set")
    p = report["paired"]["clean"]
    passed = p["sign_test"]["up"] > p["sign_test"]["down"] and p["permutation_test"]["p"] <= .05
    scores = {}
    for seed in SEEDS:
        tags = tags_for(seed_prefixes[seed])
        scores[seed] = {level: [len(sets[level][candidate_name][tag]) for tag in tags] for level in readings}
    return passed, scores


def validate_export(export, seed, registration):
    require(export["base"] == MODEL and export["revision"] == REVISION
            and export["converter_commit"] == CONVERTER and export["quantization"] == "Q8_0"
            and export["merge_dtype"] == "bfloat16", "export recipe differs from the registration")
    require(export["name"] == registration["seeds"][str(seed)]["export_name"], "export belongs to another seed")
    source = export["adapter"]
    require(source["kind"] == "cohere-curated-sft" and source["seed"] == seed
            and source["step"] == registration["steps_per_seed"]
            and source["data_sha256"] == registration["training_rows_sha256"], "adapter is not the registered final training result")
    require(integer(source["seed"], 1, 2) and integer(source["step"], 1), "invalid training identity")
    for name in ("adapter_config.json", "adapter_model.safetensors", "prepared.json", "run.json"):
        check_digest(source["files"][name])
    require(check_digest(source["prepared_sha256"]) == source["files"]["prepared.json"], "prepared training receipt differs")
    output = export["output"]
    require(output["filename"] == "model-Q8_0.gguf" and integer(output["bytes"], 1024), "invalid exported model file")
    return check_digest(output["sha256"])


def validate_precision(result, prefix):
    require(result["tag"] == prefix + "-spec20" and result["problems"] == 95 and result["draws"] == 200, "precision instrument changed")
    kept, correct, value = result["safe_kept"], result["safe_kept_reference_correct"], result["safe_precision"]
    scored = result["candidates_scored"]
    # spec_ceiling counts every kept specification before the top-three ranking.
    # The registered stage samples twenty specifications for each of 95 problems.
    require(integer(scored, 0, 95 * 20) and integer(kept, 0, scored)
            and integer(correct, 0, kept), "invalid precision counts")
    if not kept:
        require(value is None, "zero accepted specifications cannot claim precision")
        return False, None
    require(type(value) in (int, float) and math.isfinite(value)
            and math.isclose(value, correct / kept, rel_tol=0, abs_tol=1e-12), "precision disagrees with the measured counts")
    # Compare integer counts at the boundary rather than rounding a displayed ratio.
    return correct * 10 >= kept * 7, correct / kept


def validate_spec33(receipt, prefix):
    require(receipt["answer_model"] == prefix and receipt["label"] == prefix, "given-specification answers belong to another model")
    levels = receipt["levels"]
    require(levels["questions"] == 33 and levels["no row in the table"] == 0, "given-specification measurement is incomplete")
    require(integer(levels["ready"], 0, 33) and all(integer(n) for n in levels["stages"].values())
            and sum(levels["stages"].values()) == 33 and levels["stages"].get("ready", 0) == levels["ready"], "given-specification stage accounting differs")
    keys = ("proved by at least 1", "proved by at least 3", "proved by at least 5", "proved by at least 6", "proved by all seven")
    counts = [levels[name] for name in keys]
    require(all(integer(n, 0, 33) for n in counts) and counts == sorted(counts, reverse=True)
            and counts[0] <= levels["ready"], "inconsistent given-specification levels")
    passed = counts[-1] >= 27
    require(receipt["passes_spec33_requirement"] is passed, "given-specification verdict differs from its levels")
    return passed, counts[-1]


def decide(registration, development, ids, seeds, evidence_hashes):
    """Select only after the caller independently audits all referenced artifacts.

    seeds[number] contains the exact export receipt, precision result, spec33
    receipt, and the model SHA observed in each development part and precision run.
    evidence_hashes binds those independently audited inputs for the later freeze.
    """
    require(set(registration["seeds"]) == {"1", "2"} and set(seeds) == set(SEEDS)
            and all(type(seed) is int for seed in seeds), "two complete seed records are required")
    require(integer(registration["steps_per_seed"], 1), "invalid registered training length")
    check_digest(registration["training_rows_sha256"])
    panel_sha = hashlib.sha256("".join(str(i) + "\n" for i in ids).encode()).hexdigest()
    require(panel_sha == check_digest(registration["development_panel_sha256"]), "clean development panel changed")
    check_digest(registration["heldout_panel_sha256"])
    require({"t/spec_check.py", "t/recipes/spec_ceiling.py"} <= set(registration["precision_sources"])
            and {"t/score_spec_given.py", "t/recipes/grade_spec33.py"} <= set(registration["spec33_sources"]), "missing frozen grader source manifests")
    required_evidence = {"development_report", "development_audit", "registration"}
    required_evidence |= {f"seed_{seed}_{part}" for seed in SEEDS for part in ("export", "precision", "precision_receipt", "spec33_receipt", "generation_audit")}
    require(set(evidence_hashes) == required_evidence, "missing independently audited evidence bindings")
    for value in evidence_hashes.values(): check_digest(value)
    require(evidence_hashes["development_report"] == sha(development) and evidence_hashes["registration"] == sha(registration), "decision inputs differ from their bindings")
    prefixes = {s: registration["seeds"][str(s)]["prefix"] for s in SEEDS}
    dev_passed, counts = validate_development(development, ids, registration["baseline_name"], registration["candidate_name"], registration["baseline_tags"], prefixes)
    measurements, eligible = {}, []
    for seed in SEEDS:
        data = seeds[seed]; prefix = prefixes[seed]
        for field in ("export", "precision", "precision_receipt", "spec33_receipt", "generation_audit"):
            require(evidence_hashes[f"seed_{seed}_{field}"] == sha(data[field]), "seed evidence differs from its binding")
        model_sha = validate_export(data["export"], seed, registration)
        generation = data["generation_audit"]
        expected_parts = {tag_for(prefix, panel, offset) for panel in ("dev-95", "wider-145") for offset in OFFSETS}
        require(set(generation["development_models"]) == expected_parts
                and set(generation["development_models"].values()) == {model_sha}
                and generation["precision_model_sha256"] == model_sha, "a measurement used another model or omitted a part")
        precision_receipt = data["precision_receipt"]
        require(precision_receipt["grader_commit"] == "01c94ef5509fc51ab6484c1350c1cb9f8504e459"
                and precision_receipt["procedure"] == {"pool": "v5", "draws": 200, "per_problem": 3, "jobs": 4}
                and precision_receipt["source_sha256"] == registration["precision_sources"], "precision grader differs")
        require(precision_receipt["input_asset_sha256"] == generation["precision_input_asset_sha256"]
                and precision_receipt["input_manifest"] == generation["precision_input_manifest"]
                and precision_receipt["input_manifest"]["tag"] == prefix + "-spec20", "precision input evidence differs")
        spec_receipt = data["spec33_receipt"]
        require(spec_receipt["code_sha256"] == registration["spec33_sources"]
                and spec_receipt["questions"]["sha256"] == QUESTIONS_SHA, "given-specification grader or panel differs")
        require(spec_receipt["answers"]["sha256"] == generation["spec33_answers_sha256"]
                and spec_receipt["input_manifest_sha256"] == generation["spec33_input_manifest_sha256"], "given-specification input evidence differs")
        precision_ok, precision = validate_precision(data["precision"], prefix)
        specs_ok, spec33 = validate_spec33(data["spec33_receipt"], prefix)
        score = {"model_sha256": model_sha, "precision": precision, "precision_passed": precision_ok,
                 "spec33_all_seven": spec33, "spec33_passed": specs_ok,
                 "clean_counts": counts[seed]["clean"], "all_seven_counts": counts[seed]["all_seven"],
                 "mean_clean": sum(counts[seed]["clean"]) / 3,
                 "mean_all_seven": sum(counts[seed]["all_seven"]) / 3}
        measurements[str(seed)] = score
        if precision_ok and specs_ok: eligible.append(seed)
    winner = min(eligible, key=lambda seed: (-sum(counts[seed]["clean"]), -sum(counts[seed]["all_seven"]), seed)) if dev_passed and eligible else None
    return {"status": "eligible-for-heldout" if winner is not None else "not-qualified",
            "candidate": registration["candidate"], "development_passed": dev_passed,
            "development_panel_sha256": panel_sha, "heldout_panel_sha256": registration["heldout_panel_sha256"],
            "paired_clean": development["paired"]["clean"], "seeds": measurements,
            "eligible_seeds": eligible, "selected_seed": winner,
            "selected_model_sha256": measurements[str(winner)]["model_sha256"] if winner else None,
            "selection_rule": "mean clean, then mean all-seven, then lower seed number, among precision/spec33 qualifiers",
            "evidence_sha256": evidence_hashes, "heldout_started": False,
            "remaining": ["one selected held-out reading", "final laptop checks", "packaging and publication"]}


def freeze_heldout_choice(path, registration, development, ids, seeds, evidence_hashes):
    """Create an exclusive immutable choice; changed evidence cannot switch the seed."""
    decision = decide(registration, development, ids, seeds, evidence_hashes)
    require(decision["status"] == "eligible-for-heldout" and decision["selected_seed"] in SEEDS
            and decision["development_passed"] is True, "the candidate has not qualified for held-out evaluation")
    check_digest(decision["selected_model_sha256"])
    path = Path(path); record = {"decision_sha256": sha(decision), "decision": decision}
    if path.exists():
        require(canonical(json.loads(path.read_text())) == canonical(record), "held-out choice already frozen; no alternate seed or new reading")
        return record
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream: json.dump(record, stream, indent=2, allow_nan=False)
    return record
