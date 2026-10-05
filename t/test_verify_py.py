"""t/verify_py.py: a Python function the person already has, given a proved twin. The function itself, run in the
sandbox, decides what a specification and a body are worth (VERT's oracle, arXiv:2404.18852); the provers decide
the rest; and what is said is that the twin is proved and its sameness to the Python is tested."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import certificate                                              # noqa: E402
import py_sandbox                                               # noqa: E402
import spec_check                                               # noqa: E402
import verify_py                                                # noqa: E402

needs_sandbox = pytest.mark.skipif(not py_sandbox.available(), reason="no sandbox for a person's Python here")

ALL = {k: "verified / refuted" for k in spec_check.KERNELS}
DOUBLE = "def double(n: int) -> int:\n    \"\"\"Twice the number.\"\"\"\n    return 2 * n\n"


def t(ensures, body=""):
    return f"```t\nt 1\ntask double(n: int) returns (r: int)\n  ensures {ensures}\n{{\n{body}}}\n```"


SPEC, WRONG_SPEC, WEAK_SPEC = t("r == 2 * n"), t("r == 2 * n + 1"), t("r >= n or r < n")
BODY = t("r == 2 * n", "  r := 2 * n;\n")
ODD_ONE_OUT = t("r == 2 * n", "  if n == 7 {\n    r := 0;\n  } else {\n    r := 2 * n;\n  }\n")


def student(*replies):
    queue = list(replies)
    asked = []

    def decode(conversations, temperature, salt, first, max_new):
        asked.append(conversations[0])
        return [(queue.pop(0) if queue else "no answer", True, 0)]
    decode.asked = asked
    return decode


def prover(cells_for):
    return lambda tasks, jobs: {task["name"]: cells_for(task) for task in tasks}


def function(source=DOUBLE, fn=None):
    return verify_py.read_function(source, fn)


def test_the_function_is_read_with_its_annotations_its_docstring_and_the_helpers_it_calls():
    f = function("def helper(x):\n    return x * 2\n\ndef unused(x):\n    return x\n\n"
                 "def total(xs: list[int], k: int = 0) -> int:\n    'Sum plus k.'\n    return sum(helper(x) // 2 for x in xs) + k\n", "total")
    assert f["fn"] == "total" and f["kinds"] == ["list[int]", "int"] and f["doc"] == "Sum plus k."
    assert f["shown"].startswith("def total(") and "def helper(x)" in f["shown"] and "unused" not in f["shown"]


@pytest.mark.parametrize("source, fn, word", [
    ("x = (", None, "the file is not Python"),
    ("x = 1\n", None, "no top-level function"),
    ("def a(x):\n    return x\n\ndef b(x):\n    return x\n", None, "more than one function; say which with --fn (a, b)"),
    ("def a(x):\n    return x\n", "b", "no top-level function `b`"),
    ("def a(*xs):\n    return xs\n", None, "only positional parameters are read"),
    ("def a(x):\n    yield x\n", None, "is a generator"),
    ("def a():\n    return 1\n", None, "takes no parameter"),
])
def test_a_file_this_does_not_read_is_refused_with_what_to_change(source, fn, word):
    with pytest.raises(verify_py.Refused, match=word.replace("(", r"\(").replace(")", r"\)").replace("*", r"\*")):
        verify_py.read_function(source, fn)


def test_a_private_helper_beside_one_public_function_needs_no_fn():
    assert function("def _h(x):\n    return x\n\ndef f(n: int):\n    return _h(n)\n")["fn"] == "f"


@needs_sandbox
def test_with_no_example_given_the_examples_are_the_functions_own_answers():
    tests = verify_py.drawn_tests(function())
    assert tests[0] == "assert double(2) == 4" and len(tests) == verify_py.EXAMPLES
    entry, drawn = verify_py.entry_for(function(), [])
    assert drawn and entry["fn"] == "double" and entry["rec"]["text"] == "Twice the number."
    # an input the function raises on is passed over, and a tuple it returns is written as a tuple
    f = function("def pair(n: int):\n    if n < 0:\n        raise ValueError('no')\n    return (n, n + 1)\n")
    tests = verify_py.drawn_tests(f)
    assert "assert pair(2) == (2, 3)" in tests and not any("-1" in x or "-4" in x for x in tests)


@needs_sandbox
def test_a_parameter_with_no_annotation_and_no_example_is_refused_with_both_ways_out():
    with pytest.raises(verify_py.Refused, match="`n` has no annotation this reads; annotate each parameter .* or give an example with --test"):
        verify_py.entry_for(function("def double(n):\n    return 2 * n\n"), [])
    entry, drawn = verify_py.entry_for(function("def double(n):\n    return 2 * n\n"), ["assert double(3) == 6"])
    assert not drawn and entry["rec"]["text"].startswith("Write `double`, the function the Python solution below computes")


@needs_sandbox
def test_a_function_that_fails_the_persons_own_example_is_said_before_any_model_is_asked():
    with pytest.raises(verify_py.Refused, match=r"your function fails your own example `assert double\(3\) == 7`"):
        verify_py.entry_for(function(), ["assert double(3) == 7"])
    with pytest.raises(verify_py.Refused, match="the examples call `twice`, and the function is `double`"):
        verify_py.entry_for(function(DOUBLE + "\ndef twice(n):\n    return 2 * n\n", "double"), ["assert twice(3) == 6"])


@needs_sandbox
def test_a_specification_then_a_body_that_answers_as_the_function_does_and_is_proved_is_shown():
    entry, _ = verify_py.entry_for(function(), ["assert double(3) == 6", "assert double(0) == 0"])
    model = student(SPEC, BODY)
    r = verify_py.by_specification(entry, function(), model, specs=1, answers=1, prover=prover(lambda task: dict(ALL, lean="timeout / refuted")))
    s = r["shown"]
    assert s["proved by"] == 6 and s["undecided"] == ["lean"] and s["specification"] == ["ensures r == 2 * n"]
    assert s["same as yours on"] >= 10 and s["behind the specification"]["mutated outputs rejected"] == 1.0
    # the model was shown the function both times: first for the specification, then for the body
    assert all("def double(n: int) -> int:" in conversation[-1]["content"] for conversation in model.asked) and len(model.asked) == 2
    text = verify_py.render(r)
    assert text.startswith("VERIFIED: a proved twin of `double`: proved by 6 of 7 provers")
    assert "tested on the inputs counted here, not proved" in text


@needs_sandbox
def test_a_specification_false_at_the_functions_own_answers_never_reaches_a_body():
    entry, _ = verify_py.entry_for(function(), ["assert double(3) == 6", "assert double(0) == 0"])
    model = student(WRONG_SPEC, WEAK_SPEC)
    r = verify_py.by_specification(entry, function(), model, specs=2, answers=1, prover=prover(lambda task: ALL))
    assert r["shown"] is None and len(model.asked) == 2 and r["bodies asked"] == 0
    assert r["why"].startswith("no specification the model wrote holds at your function's answers")
    assert verify_py.render(r).startswith("NOT VERIFIED: no specification the model wrote holds")
    assert "specification 1: `r == 2 * n + 1` is false at your function's own answer `double(3) == 6`" in r["refused"]
    assert any(x.startswith("specification 2: `r >= n or r < n` says too little: it accepts 100% of the wrong results") for x in r["refused"])


@needs_sandbox
def test_a_function_that_does_not_do_what_its_docstring_says_is_pointed_at_with_the_example():
    # the docstring promises 1 + ... + n; the loop stops one short, and the examples are the function's own answers
    source = 'def triangle(n: int) -> int:\n    """The sum 1 + 2 + ... + n."""\n    return sum(range(n))\n'
    f = verify_py.read_function(source)
    entry, drawn = verify_py.entry_for(f, [])
    promised = "```t\nt 1\ntask triangle(n: int) returns (r: int)\n  requires n >= 0\n  ensures r == n * (n + 1) / 2\n{\n}\n```"
    r = verify_py.by_specification(entry, f, student(promised), specs=1, answers=1, prover=prover(lambda task: ALL))
    assert r["shown"] is None and drawn
    assert "specification 1: `r == n * (n + 1) / 2` is false at your function's own answer `triangle(2) == 1`" in r["refused"]
    assert "either the model misread the docstring, or the function does not do what it says" in r["why"]


@needs_sandbox
def test_a_body_that_parts_from_the_function_on_one_input_is_refused_with_that_input_and_the_next_is_tried():
    entry, _ = verify_py.entry_for(function(), ["assert double(3) == 6", "assert double(0) == 0"])
    called = []

    def proving(tasks, jobs):
        called.append([task["name"] for task in tasks])
        return {task["name"]: ALL for task in tasks}
    r = verify_py.by_specification(entry, function(), student(SPEC, ODD_ONE_OUT, BODY), specs=1, answers=2, prover=proving)
    assert r["shown"] and len(called) == 1                       # the odd one never reached a prover
    assert any("it does not answer as your function does (`double(*[7]) == 0`" in x for x in r["refused"]), r["refused"]


@needs_sandbox
def test_a_body_no_prover_proves_or_one_refutes_is_not_shown():
    entry, _ = verify_py.entry_for(function(), ["assert double(3) == 6", "assert double(0) == 0"])
    r = verify_py.by_specification(entry, function(), student(SPEC, BODY), specs=1, answers=1,
                         prover=prover(lambda task: dict(ALL, dafny="refuted / refuted")))
    assert r["shown"] is None and r["refused"] == ["specification 1, body 1: refuted by dafny"]
    assert r["why"] == "no body the model wrote answered as your function does and was proved"


@needs_sandbox
def test_the_command_writes_the_twin_its_python_and_a_certificate_that_replays(tmp_path, monkeypatch, capsys):
    source = tmp_path / "double.py"
    source.write_text(DOUBLE, encoding="utf-8")
    real = verify_py.verify
    monkeypatch.setattr(verify_py, "verify", lambda entry, f, model, specs, answers, max_new=1024, jobs=2, whole=5:
                        real(entry, f, student(BODY), 1, 1, prover=prover(lambda task: ALL), whole=1))
    monkeypatch.setattr(verify_py.python_beside, "api_decode", lambda *a, **k: None)
    out_t, out_py, out_c = tmp_path / "double.t", tmp_path / "proved.py", tmp_path / "double.cert.json"
    assert verify_py.main(["--student", "h:1", "--file", str(source), "--save-t", str(out_t), "--save-python", str(out_py),
                           "--certificate", str(out_c)]) == 0
    said = capsys.readouterr().out
    assert said.startswith("No example was given, so these were taken from your function itself:\n  assert double(2) == 4")
    assert "task double(n: int)" in out_t.read_text() and "def double(n):" in out_py.read_text()
    c = json.loads(out_c.read_text())
    assert c["predicate"]["kind"] == "verify" and c["predicate"]["reference python"] == DOUBLE
    report = certificate.check(c, prover=prover(lambda task: ALL))
    assert report["verdict"] == certificate.REPRODUCED, report
    original = next(s for s in report["steps"] if s["what"] == "original")
    assert original["result"] == "ok" and "answers as the recorded function does" in original["detail"]
    # the same certificate with another function recorded is not this twin's
    c["predicate"]["reference python"] = DOUBLE.replace("2 * n", "2 * n + (n == 5)")
    c["subject"] = [{"name": n, "digest": {"sha256": certificate.digest(x)}} for n, x in certificate._artifacts(c["predicate"])]
    report = certificate.check(c, prover=prover(lambda task: ALL))
    assert report["verdict"] == certificate.FAILED and {s["what"] for s in report["steps"] if s["result"] == "FAILED"} >= {"original"}


@needs_sandbox
def test_whole_answers_are_tried_first_and_the_function_is_the_oracle_without_being_shown():
    entry, _ = verify_py.entry_for(function(), ["assert double(3) == 6", "assert double(0) == 0"])
    wrong = t("r == 2 * n + 1", "  r := 2 * n + 1;\n")          # fails the examples: never judged
    weak = t("r >= n or r < n", "  r := 2 * n;\n")              # passes them, and its specification says nothing
    model = student(wrong, weak, BODY)
    r = verify_py.by_answers(entry, function(), model, answers=3, prover=prover(lambda task: ALL))
    s = r["shown"]
    assert s["proved by"] == 7 and s["specification"] == ["ensures r == 2 * n"] and s["same as yours on"] >= 10
    assert r["answers asked"] == 3 and len(model.asked) == 3
    # the question is `ask`'s: the docstring and the examples; the function's code is not in it
    assert all("Twice the number." in c[-1]["content"] and "return 2 * n" not in c[-1]["content"] for c in model.asked)
    assert any(x.startswith("answer 1: fails") for x in r["refused"]) and any(x.startswith("answer 2: `r >= n or r < n`") for x in r["refused"])
    assert verify_py.render(r).startswith("VERIFIED: a proved twin of `double`")


@needs_sandbox
def test_an_answer_that_passes_the_examples_and_is_not_the_function_is_not_shown():
    entry, _ = verify_py.entry_for(function(), ["assert double(3) == 6", "assert double(0) == 0"])
    r = verify_py.by_answers(entry, function(), student(ODD_ONE_OUT), answers=1, prover=prover(lambda task: ALL))
    assert r["shown"] is None and r["why"].startswith("no whole answer the model wrote held at your function's answers")
    assert any("it does not answer as your function does" in x or "is false at your function's own answer" in x for x in r["refused"])
    unproved = verify_py.by_answers(entry, function(), student(BODY), answers=1, prover=prover(lambda task: {k: "timeout / refuted" for k in ALL}))
    assert unproved["shown"] is None and unproved["refused"] == ["answer 1: no prover proved it"]


@needs_sandbox
def test_verify_falls_back_to_writing_the_specification_first_and_says_which_route_showed_the_twin():
    entry, _ = verify_py.entry_for(function(), ["assert double(3) == 6", "assert double(0) == 0"])
    proving = prover(lambda task: ALL)
    first = verify_py.verify(entry, function(), student(BODY), whole=1, prover=proving)
    assert first["route"] == "answers" and first["shown"]["proved by"] == 7 and "specifications asked" not in first
    # no whole answer is usable: the specification is then written from the function, and a body proved for it
    model = student("no t here", SPEC, BODY)
    second = verify_py.verify(entry, function(), model, specs=1, answers=1, whole=1, prover=proving)
    assert second["route"] == "specification" and second["shown"]["proved by"] == 7 and second["answers asked"] == 1
    assert second["refused"][0].startswith("answer 1:") and len(model.asked) == 3
    assert "def double(n: int) -> int:" in model.asked[1][-1]["content"]                 # only this route shows the function
    nothing = verify_py.verify(entry, function(), student(), specs=1, answers=1, whole=1, prover=proving)
    assert nothing["shown"] is None and "route" not in nothing and nothing["why"].startswith("no specification the model wrote")
    assert [x.split(":")[0] for x in nothing["refused"]] == ["answer 1", "specification 1"]
    # whole=0 is the specification route alone, as V1 was measured
    assert "answers asked" not in verify_py.verify(entry, function(), student(SPEC, BODY), specs=1, answers=1, whole=0, prover=proving)
