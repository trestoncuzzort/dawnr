"""s2 is s1 with nested sequence types spelled as the language spells them (2026-10-01)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402


def _entry(arg_kind, ret_kind):
    return {"rec": {"text": "Write a function to do a thing.", "test_list": ["assert f(1) == 1"]},
            "points": [{"ok": True, "fn": "f", "args": [[arg_kind, []], ["int", 1]], "expected": [ret_kind, []]}],
            "fn": "f"}


def test_s2_spells_a_nested_sequence_as_the_language_does():
    user = se.build_prompt(_entry("seq-of-seq", "seq-of-seq"), "s2")[1]["content"]
    assert "seq-of-seq" not in user
    assert "of type(s) seq<seq>, int," in user and "returning seq<seq>." in user


def test_the_spelling_s2_prints_is_one_the_parser_accepts():
    task = surface.parse("t 1\ntask f(a: seq<seq>, n: int) returns (r: seq<seq>)\n  ensures r == a\n{\n  r := a;\n}\n")
    assert task["params"][0]["type"] == {"seq": "seq"}


def test_s2_is_s1_when_no_type_is_nested():
    e = _entry("seq", "int")
    assert se.build_prompt(e, "s2") == se.build_prompt(e, "s1")


def test_s1_is_unchanged_and_shares_the_system_text():
    e = _entry("seq-of-seq", "seq")
    s1, s2 = se.build_prompt(e, "s1"), se.build_prompt(e, "s2")
    assert "of type(s) seq-of-seq, int," in s1[1]["content"]
    assert s1[0] == s2[0] == {"role": "system", "content": se.STUDENT_SYSTEM}
