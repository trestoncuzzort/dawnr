"""--seed-offset shifts every sampling salt (the stage number the server route seeds from) and nothing else, so a second
decode of the same model differs only in its sampled attempts (t/PREDICT-2026-10-22-seed-variance.md)."""
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mbpp_dfy                                                 # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402
import surface                                                  # noqa: E402


def _entry(*asserts):
    pts = [mbpp_dfy.parse_assertion(a, strings=True, nested_strings=True) for a in asserts]
    return se.mark_characters({"rec": {"text": "Write a function to square a number.", "test_list": list(asserts)},
                               "points": pts, "fn": "square"})


ENTRY = _entry("assert square(3) == 9", "assert square(4) == 16", "assert square(0) == 0")
SPEC = surface.parse("t 1\ntask square(n: int) returns (r: int)\n  ensures r == n * n\n{\n}\n")
TASK = "```t\nt 1\ntask square(n: int) returns (r: int)\n  ensures r == n * n\n{\n  r := n + n;\n}\n```"


def _outdir(root, tag):
    d = root / tag
    (d / "raw").mkdir(parents=True, exist_ok=True)
    return d


def _fake_student():
    mod = types.ModuleType("student_generate")
    seeds = []
    mod.load = lambda _m: (None, None)
    mod.problem_seed = lambda stage, _first: stage
    def decode(_m, _t, conversations, _max_new, _temp, _top_p, seed=None):
        seeds.append(seed)
        return [(TASK, True, 1) for _ in conversations]
    mod.decode, mod.seeds = decode, seeds
    return mod


def _run(tmp_path, monkeypatch, tag, extra):
    ids = tmp_path / f"{tag}.txt"; ids.write_text("1\n")
    given = tmp_path / f"{tag}.jsonl"
    given.write_text(json.dumps({"task_id": 1, "tasks": [SPEC], "sources": ["lab/a"]}) + "\n")
    monkeypatch.setattr(se, "pool", lambda version: {1: ENTRY})
    monkeypatch.setattr(se, "OUT_ROOT", tmp_path)
    monkeypatch.setattr(se, "outdir", lambda t: _outdir(tmp_path, t))
    student = _fake_student()
    monkeypatch.setitem(sys.modules, "student_generate", student)
    assert spec_first.main(["--model", "none", "--given-specs", str(given), "--tag", tag, "--ids-file", str(ids),
                            "--samples", "2", *extra]) == 0
    return student.seeds


def test_the_offset_shifts_every_proof_stage_salt(tmp_path, monkeypatch):
    plain = _run(tmp_path, monkeypatch, "s0", [])
    shifted = _run(tmp_path, monkeypatch, "s1", ["--seed-offset", "1000"])
    assert plain == [0, 1, 2] and shifted == [1000, 1001, 1002]
