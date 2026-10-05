"""t/larger_inputs.py and spec_check.larger_inputs: the specification check on inputs larger than a problem's
examples, added to verdicts written before it existed. The case is the one found in the published scoreboard on
2026-10-05: a specification that lists the answers for the sizes the examples reach (QuickCheck grows its sizes;
EvalPlus, arXiv:2305.01210)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import larger_inputs                                            # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

ENTRY = {"rec": {"text": "The sum of the fifth powers of the first n even numbers.", "test_list": ["assert even_Power_Sum(2) == 1056"],
                 "code": "def even_Power_Sum(n):\n    return sum((2 * i) ** 5 for i in range(1, n + 1))\n"},
         "fn": "even_Power_Sum", "points": [{"ok": True, "fn": "even_Power_Sum", "args": [["int", 2]], "expected": ["int", 1056]}]}
TABLE = surface.parse("""t 1
task even_Power_Sum(n: int) returns (r: int)
  requires n >= 0
  ensures n == 0 ==> r == 0
  ensures n == 1 ==> r == 32
  ensures n == 2 ==> r == 1056
  ensures n == 3 ==> r == 8832
  ensures n == 4 ==> r == 41600
{
  r := 0;
}
""")
SUM = surface.parse("""t 1
task even_Power_Sum(n: int) returns (r: int)
  requires n >= 0
  ensures r == s5(n)
spec fun s5(n: int): int
  decreases n
= if n <= 0 then 0 else s5(n - 1) + 2 * n * (2 * n) * (2 * n) * (2 * n) * (2 * n)
{
  r := 0;
}
""")


def test_a_table_of_the_small_cases_is_complete_on_the_ordinary_draws_and_says_nothing_on_larger_ones():
    import random
    ordinary = spec_check.check_task(TABLE, ENTRY, 200, random.Random(1))
    assert ordinary["status"] == "agrees" and spec_check.complete(ordinary, 0.6) is not False   # every draw is 0..4
    larger = spec_check.larger_inputs(TABLE, ENTRY, "1:x")
    assert larger["status"] == "agrees" and larger["completeness"] < 0.2
    assert spec_check.larger_reason(larger) == "the specification says too little about inputs larger than the examples"
    assert larger["weak_witness"]["args"][0] > 4
    honest = spec_check.larger_inputs(SUM, ENTRY, "1:x")
    assert honest["completeness"] == 1.0 and spec_check.larger_reason(honest) is None
    assert spec_check.larger_inputs(TABLE, ENTRY, "1:x") == larger                         # its own generator: the same every time
    assert spec_check.larger_reason(None) is None and spec_check.larger_reason({"status": "no valid draws"}) is None


def test_older_verdicts_are_given_the_measurement_and_nothing_else_in_them_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(se, "pool", lambda version: {271: ENTRY})
    monkeypatch.setattr(larger_inputs, "_POOL", {})
    d = tmp_path / se.model_tag("set") / "tasks"
    d.mkdir(parents=True)
    for name, task in (("table", TABLE), ("sum", SUM), ("gone", None)):
        if task is not None:
            (d / f"{name}.json").write_text(json.dumps(dict(task, name=name)), encoding="utf-8")
    verdicts = {"set/table": {"status": "agrees", "draws": 200, "completeness": 1.0, "task_id": 271, "seed": 1, "pool": "v5"},
                "set/sum": {"status": "agrees", "draws": 200, "completeness": 1.0, "task_id": 271, "seed": 1},
                "set/gone": {"status": "agrees", "draws": 200, "task_id": 271},          # its task file is no longer there
                "set/wrong": {"status": "disagrees", "task_id": 271},
                "other/table": {"status": "agrees", "task_id": 271}}
    out, counts = larger_inputs.add(verdicts, ["set"], "v5", jobs=1, root=tmp_path)
    assert counts == {"agreeing verdicts": 4, "measured": 2, "do not stand on larger inputs": 1, "not measured": 0}
    assert spec_check.larger_reason(out["set/table"]["larger"]) and spec_check.larger_reason(out["set/sum"]["larger"]) is None
    assert "larger" not in out["set/gone"] and "larger" not in out["set/wrong"] and "larger" not in out["other/table"]
    assert {k: v for k, v in out["set/table"].items() if k != "larger"} == verdicts["set/table"] and "larger" not in verdicts["set/table"]


def test_the_command_refuses_to_write_over_the_verdicts_it_reads(tmp_path):
    f = tmp_path / "v.json"
    f.write_text('{"results": {}}')
    try:
        larger_inputs.main(["--verdicts", str(f), "--out", str(f)])
    except SystemExit as stop:
        assert "must be another file" in str(stop)
    else:
        raise AssertionError("it wrote over its input")
    assert larger_inputs.main(["--verdicts", str(f), "--out", str(tmp_path / "w.json")]) == 0
    assert json.loads((tmp_path / "w.json").read_text())["larger_inputs"]["draws"] == spec_check.LARGER_DRAWS
