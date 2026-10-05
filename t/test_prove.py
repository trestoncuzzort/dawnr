"""t/prove.py: from a specification. A body counts only if it keeps the person's specification and is proved;
the specification itself is measured, because a proof says nothing about whether it is what was meant
(Lahiri, arXiv:2406.09757; SAFE's completeness, arXiv:2410.15756)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import answer                                                   # noqa: E402
import prove                                                    # noqa: E402
import py_sandbox                                               # noqa: E402
import spec_check                                               # noqa: E402
import surface                                                  # noqa: E402

ALL = {k: "verified / refuted" for k in spec_check.KERNELS}

SPEC = """t 1
gate loops
task total(a: seq) returns (r: int)
  ensures r == sum_to(a, len(a))
spec fun sum_to(s: seq, n: int): int
  decreases n
= if n <= 0 then 0 else sum_to(s, n - 1) + s[n - 1]
{
}
"""
BODY = """  r := 0;
  var i: int := 0;
  while i < len(a)
    invariant 0 <= i and i <= len(a)
    invariant r == sum_to(a, i)
    decreases len(a) - i
  {
    r := r + a[i];
    i := i + 1;
  }
"""
RIGHT = "```t\n" + SPEC.replace("{\n}\n", "{\n" + BODY + "}\n") + "```"
DROPPED = RIGHT.replace("  ensures r == sum_to(a, len(a))\n", "  ensures r >= 0 or r < 0\n")
WEAK_SPEC = "t 0\ntask clamp(x: int) returns (r: int)\n  ensures r >= 0\n{\n}\n"
WEAK_BODY = "```t\nt 0\ntask clamp(x: int) returns (r: int)\n  ensures r >= 0\n{\n  if x < 0 {\n    r := 0;\n  } else {\n    r := x;\n  }\n}\n```"


def student(*replies):
    queue = list(replies)

    def decode(conversations, temperature, salt, first, max_new):
        return [(queue.pop(0) if queue else "no answer", True, 0)]
    return decode


def prover(cells_for):
    return lambda tasks, jobs: {t["name"]: cells_for(t) for t in tasks}


def spec(text=SPEC):
    return prove.read_spec(text)


def test_a_body_that_keeps_the_specification_and_is_proved_is_shown():
    r = prove.prove(spec(), student(RIGHT), answers=1, prover=prover(lambda t: dict(ALL, rocq="timeout / refuted")))
    s = r["shown"]
    assert s["proved by"] == 6 and s["undecided"] == ["rocq"]
    assert "task total(a: seq)" in s["program"] and "invariant r == sum_to(a, i)" in s["program"]
    text = prove.render_proof(r)
    assert text.startswith("PROVED: by 6 of 7 provers") and "the specification is yours, unchanged" in text


def test_the_question_asked_is_the_training_rows_own():
    asked = []

    def decode(conversations, temperature, salt, first, max_new):
        asked.append(conversations[0])
        return [(RIGHT, True, 0)]
    prove.prove(spec(), decode, answers=1, prover=prover(lambda t: dict(ALL)))
    assert asked[0][-1]["content"].startswith("Complete this t task. Keep its header, parameters, requires, ensures")
    assert "task total(a: seq)" in asked[0][-1]["content"] and "invariant r ==" not in asked[0][-1]["content"]


def test_an_answer_that_drops_an_ensures_is_refused_and_never_reaches_a_prover():
    called = []
    r = prove.prove(spec(), student(DROPPED), answers=1, prover=lambda tasks, jobs: called.append(tasks) or {})
    assert r["shown"] is None and not called
    assert "it changed the specification" in r["refused"][0]
    assert prove.render_proof(r).startswith("NOT PROVED: no answer kept the specification")


def test_the_answer_most_provers_prove_is_the_one_shown_and_a_refuted_one_never_is():
    second = RIGHT.replace("invariant 0 <= i and i <= len(a)", "invariant 0 <= i and i <= len(a) and true")

    def cells(t):
        if t["name"].startswith("answer_1__"):
            return dict(ALL, lean="refuted / refuted")
        return dict(ALL, spark="timeout / refuted")
    r = prove.prove(spec(), student(RIGHT, second), answers=2, prover=prover(cells))
    assert r["shown"]["answer"] == 2 and r["shown"]["proved by"] == 6
    assert r["refused"] == ["answer 1: refuted by lean"]


def test_a_renamed_answer_is_the_same_answer_and_a_reply_that_never_came_is_named():
    renamed = RIGHT.replace("task total(", "task mbpp_1__total(")
    r = prove.prove(spec(), student("", renamed), answers=2, prover=prover(lambda t: dict(ALL)))
    assert r["shown"]["answer"] == 2 and r["refused"] == ["answer 1: no reply from the model"]
    assert "task total(a: seq)" in r["shown"]["program"]


def test_a_file_with_a_body_is_proved_as_written_and_no_model_is_asked():
    full = spec(RIGHT)
    r = prove.prove(full, None, prover=prover(lambda t: dict(ALL)))
    assert r["shown"]["proved by"] == 7 and r["wrote the body"] == "the file" and r["answers asked"] == 0
    assert "The body was written by the file" in prove.render_proof(r)


def test_a_specification_that_pins_the_result_down_says_so():
    q = prove.pins_down(spec(RIGHT))
    assert q["inputs"] >= 10 and q["completeness"] == 1.0 and q["witness"] is None


def test_a_weak_specification_is_proved_and_the_person_is_told_what_else_it_accepts():
    r = prove.prove(spec(WEAK_SPEC), student(WEAK_BODY), answers=1, prover=prover(lambda t: dict(ALL)))
    q = r["shown"]["specification"]
    assert r["shown"]["proved by"] == 7 and q["completeness"] < prove.WEAK
    w = q["witness"]
    assert w["also_accepted"] != w["right"] and w["also_accepted"] >= 0
    text = prove.render_proof(r)
    assert "Your specification says little" in text and "would also accept" in text and "add an `ensures`" in text


def test_a_file_that_is_not_a_specification_is_refused_with_why():
    with pytest.raises(prove.Refused, match="not a t task"):
        prove.read_spec("def f(x): return x")
    with pytest.raises(prove.Refused, match="no `ensures`"):
        prove.read_spec("t 0\ntask f(x: int) returns (r: int)\n{\n}\n")
    assert prove.read_spec("Here it is:\n\n```t\n" + SPEC + "```\n")["name"] == "total"       # fenced is fine


@pytest.mark.skipif(not py_sandbox.available(), reason="bubblewrap is not installed")
def test_the_proved_program_comes_back_as_python_under_the_specifications_name(tmp_path, monkeypatch):
    r = prove.prove(spec(), student(RIGHT), answers=1, prover=prover(lambda t: dict(ALL)))
    py = r["shown"]["python"]
    assert py["source"].startswith("def total(a):") and py["inputs"] >= 10
    scope = {}
    exec(py["source"], scope)                                   # noqa: S102 -- the translator's own output
    assert scope["total"]([1, 2, 3]) == 6
    # the command writes both files
    path = tmp_path / "total.t"
    path.write_text(SPEC)
    monkeypatch.setattr(prove, "prove", lambda *a, **k: r)
    monkeypatch.setattr(prove.python_beside, "api_decode", lambda *a, **k: None)
    out_py, out_t = tmp_path / "total.py", tmp_path / "proved.t"
    assert prove.main(["prove", "--student", "h:1", "--spec", str(path), "--save-python", str(out_py), "--save-t", str(out_t)]) == 0
    assert out_py.read_text().startswith("def total(a):") and "invariant r == sum_to(a, i)" in out_t.read_text()


# ---- spec: candidate specifications for a question in words ----

ENTRY = answer.entry_of("Double a number.", ["assert double(3) == 6", "assert double(0) == 0"])


def task(ensures, body="r := 2 * n;"):
    return f"```t\nt 1\ntask double(n: int) returns (r: int)\n  ensures {ensures}\n{{\n  {body}\n}}\n```"


EXACT, SAME_AGAIN, WEAK, OTHER = (task("r == 2 * n"), task("r == 2 * n", "r := n + n;"), task("n >= 0 ==> r >= n"),
                                   task("r == n * n - n", "r := n * n - n;"))
PYTHON = "```python\ndef double(n):\n    return 2 * n\n```"
needs_sandbox = pytest.mark.skipif(not py_sandbox.available(), reason="bubblewrap is not installed")


def python(reply=PYTHON):
    return lambda conversations, temperature, salt, first, max_new: [(reply, True, 0)]


@needs_sandbox
def test_distinct_supported_specifications_are_shown_once_each_with_who_wrote_them():
    r = prove.propose(ENTRY, student(EXACT, SAME_AGAIN, WEAK, OTHER), python(), answers=4)
    specs = r["specifications"]
    assert len(specs) == 1 and specs[0]["written by"] == [1, 2]            # two bodies, one specification
    assert specs[0]["text"].rstrip().endswith("{\n}") and "ensures r == 2 * n" in specs[0]["text"]
    assert specs[0]["completeness"] == 1.0 and specs[0]["draws"] >= 10
    assert any("weak specification" in x for x in r["refused"])
    text = prove.render_specs(r)
    assert text.startswith("1 specification for double") and "[1] written by 2 of 4 answers" in text


@needs_sandbox
def test_no_supported_specification_is_said_plainly():
    r = prove.propose(ENTRY, student(WEAK), python(), answers=1)
    assert r["specifications"] == [] and prove.render_specs(r).startswith("NO SPECIFICATION:")


@needs_sandbox
def test_a_saved_specification_is_one_prove_reads(tmp_path, monkeypatch):
    r = prove.propose(ENTRY, student(EXACT), python(), answers=1)
    monkeypatch.setattr(prove, "propose", lambda *a, **k: r)
    monkeypatch.setattr(prove.python_beside, "api_decode", lambda *a, **k: None)
    out = tmp_path / "double.t"
    argv = ["spec", "--student", "h:1", "--python", "h:2", "--text", "Double a number.", "--test", "assert double(3) == 6",
            "--save", str(out)]
    assert prove.main(argv) == 0
    saved = prove.read_spec(out.read_text())
    assert saved["name"] == "double" and saved["body"] == [] and len(saved["ensures"]) == 1
    assert prove.main(argv + ["--pick", "3"]) == 0 and "ensures r == 2 * n" in out.read_text()   # no third: file untouched
