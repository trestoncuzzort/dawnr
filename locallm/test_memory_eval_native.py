"""memory_eval_native.py: dawnr's real recall supplies the memory; a pretrained model reads it in a system turn;
memory_eval.judge judges the reply unchanged."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "t"))

import memory_eval  # noqa: E402
import memory_eval_native as men  # noqa: E402


def test_the_memory_is_a_labelled_system_turn_and_nothing_is_added_without_it():
    item = {"user": "What do you remember about me?"}
    with_span = men.messages_for(item, ["prefers `xs` for a sequence parameter"])
    assert with_span[0] == {"role": "system", "content": men.MEMORY_HEAD + "\nprefers `xs` for a sequence parameter"}
    assert with_span[1] == {"role": "user", "content": item["user"]}
    assert men.messages_for(item, []) == [{"role": "user", "content": item["user"]}]
    sys_too = men.messages_for(item, ["m"], system="S")
    assert sys_too[0]["content"].startswith("S\n\n" + men.MEMORY_HEAD)


def test_a_fenced_program_is_the_answer_the_judge_reads():
    program = "t 1\ntask f(xs: seq) returns (r: int)\n  ensures r == len(xs)\n{\n  r := len(xs);\n}\n"
    parts = men.parts_of("Here it is:\n```t\n" + program + "```")
    assert parts[-1] == {"type": "t", "text": program.strip("\n") + "\n"} or parts[-1]["text"].strip() == program.strip()
    item = {"id": "recall:with:x", "category": "recall", "span": True, "preference": "xs"}
    got = memory_eval.judge(item, men.parts_of("You prefer `xs` for a sequence parameter."), True)
    assert got["correct"] is True


def test_the_real_recall_returns_the_stored_fact_and_nothing_for_an_empty_store(tmp_path):
    with_fact = {"id": "recall:with:t1", "user": "What do you remember about me?",
                 "fact_text": "uses `xseq` for a sequence parameter. (canary-1)"}
    without = {"id": "recall:without:t1", "user": "What do you remember about me?"}
    got = men.recalled(with_fact, tmp_path)
    assert got and "xseq" in "\n".join(got)
    assert men.recalled(without, tmp_path) == []
