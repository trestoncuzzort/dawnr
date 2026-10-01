"""t/idiom_hints.py: a parse refusal names the t idiom for the construct that was written
(AutoVerus's error-type-specific repair instructions, arXiv:2409.13082). Every example a hint
shows must itself be valid t."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import debug_rows                                               # noqa: E402
import fuzz_lower                                               # noqa: E402
import idiom_hints                                              # noqa: E402
import surface                                                  # noqa: E402

HEAD = "t 1\ngate loops\ntask f(s: seq, n: int) returns (r: int)\n"
BODY = "{\n  r := 0;\n}\n"


def refused(ensures, head=HEAD):
    block = head + f"  ensures {ensures}\n" + BODY
    try:
        surface.parse(block)
    except surface.SurfaceError as e:
        return block, str(e)
    raise AssertionError(f"this parses, so it is no test of a hint: {ensures}")


def test_each_class_is_recognised_on_the_line_the_parser_stops_at():
    for ensures, cls in [("r == len([x in s . x < 0])", "comprehension"),
                         ("r == sum([s[i] for i in [0, n)])", "comprehension"),
                         ("exists k: int . n == 2 * k", "unbounded quantifier"),
                         ("exists a b such that a * b == n", "unbounded quantifier"),
                         ("forall x in s . x >= 0", "element quantifier"),
                         ("r == n ** 2", "power"),
                         ("r >= 0 && n >= 0", "boolean operators"),
                         ("r == len(s[1:n])", "python slice")]:
        block, why = refused(ensures)
        assert idiom_hints.classify(block, why)[0] == cls, (ensures, why)
    block, why = refused("len(r) == 0", head="t 1\ngate loops\ntask f(s: seq) returns (r: seq of seq)\n")
    assert idiom_hints.classify(block, why)[0] == "nested type"


def test_a_refusal_with_no_known_construct_or_no_position_gets_no_hint():
    block, why = refused("r == == n")
    assert idiom_hints.hint(block, why) is None
    assert idiom_hints.hint(block, "no position here") is None
    assert idiom_hints.hint(block, None) is None


def test_the_counting_example_is_valid_t_and_counts():
    src = ("t 1\ngate loops\ntask count_negative(s: seq) returns (r: int)\n  ensures r == count_neg(s, len(s))\n"
           + idiom_hints.COUNT_EXAMPLE + "\n{\n  r := 0;\n  var i: int := 0;\n  while i < len(s)\n    invariant 0 <= i\n"
           "    invariant i <= len(s)\n    invariant r == count_neg(s, i)\n    decreases len(s) - i\n  {\n"
           "    if s[i] < 0 {\n      r := r + 1;\n    } else {\n    }\n    i := i + 1;\n  }\n}\n")
    task = surface.parse(src)
    assert fuzz_lower.check_wf(task) == []
    import interp
    env = {"s": (1, -2, 3, -4), "r": None}
    interp.exec_body(task["body"], env, interp.funs_of(task, task["body"]), interp.St())
    assert env["r"] == 2


def test_the_other_idioms_the_hints_name_are_valid_t():
    for ensures in ("exists k in [0, n + 1) . n == 2 * k", "forall i in [0, len(s)) . s[i] >= 0",
                    "r >= 0 and not (n < 0) or r == 0", "len(s[0..0]) == 0"):
        surface.parse(HEAD + f"  ensures {ensures}\n" + BODY)
    surface.parse("t 1\ngate loops\ntask f(s: seq<seq>) returns (r: int)\n  ensures r == 0\n" + BODY)


def test_the_parse_message_carries_the_hint_when_the_attempt_is_given_and_is_unchanged_without_it():
    block, why = refused("r == len([x in s . x < 0])")
    kind, said = debug_rows.message_for("parse", why, None, None, None, attempt=block)
    assert kind == "parse" and said.startswith("The t checker rejected it: " + why)
    assert "t has no comprehension" in said and "spec fun count_neg" in said
    assert debug_rows.message_for("parse", why, None, None, None) == ("parse", "The t checker rejected it: " + why)
    plain, why2 = refused("r == == n")
    assert debug_rows.message_for("parse", why2, None, None, None, attempt=plain)[1] == "The t checker rejected it: " + why2
