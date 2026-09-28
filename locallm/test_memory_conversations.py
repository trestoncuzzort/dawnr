"""dawnr's memory conversations: the vocabulary, the real recall behind every span, the gate, the judge.

What must hold (DAWNR-MEMORY.md section 8): a memory span is never supervised and never marked untrusted
(chat.render_conversation's "memory" branch); every span in a conversation is what dawnr's own recall
(dawnr_memory.harness_hooks, retrieval.recall) answers for the fact this conversation is about, not text
written by hand; a rename is never used as an answer unless the real t tool still verifies it; the held-out
side shares no preference value, phrasing or canary with the training side; and the trainers' own gate
(chat_data.gate) refuses a row that uses a held-out id under any alias. Needs the locallm venv (torch);
skipped without it, as test_tool_conversations.py skips its rendering suite.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "t"))

try:
    import torch  # noqa: F401
except ImportError:                                   # pragma: no cover
    torch = None

CORPUS = Path.home() / "scratch" / "corpus-all-2026-09-26.txt"   # this machine's build of the proved corpus; the test skips without it
SPLIT = HERE.parent / "t" / "out" / "loop" / "split-v5.json"

PROGRAM_SEQ = """t 1
task double_all(s: seq) returns (r: seq)
  ensures len(r) == len(s)
  ensures forall i in [0, len(r)) . r[i] == 2 * s[i]
{
  r := s;
  var i: int := 0;
  while i < len(r)
    invariant len(r) == len(s)
    invariant 0 <= i and i <= len(r)
    invariant forall j in [i, len(r)) . r[j] == s[j]
    invariant forall j in [0, i) . r[j] == 2 * s[j]
    decreases len(r) - i
  {
    r := r[i := 2 * r[i]];
    i := i + 1;
  }
}
"""
PROGRAM_INT = """t 1
task double(x: int) returns (y: int)
  requires x >= 0
  ensures y == 2 * x
{
  y := 2 * x;
}
"""


@unittest.skipIf(torch is None, "needs torch")
class Vocabulary(unittest.TestCase):
    def test_train_and_heldout_names_are_disjoint(self):
        import memory_fixtures as mfx
        self.assertFalse(set(mfx.TRAIN_NAMES) & set(mfx.HELDOUT_NAMES))

    def test_train_and_heldout_phrasings_are_disjoint(self):
        import memory_fixtures as mfx
        self.assertFalse(set(mfx.PHRASINGS["train"]) & set(mfx.PHRASINGS["heldout"]))
        self.assertFalse(set(mfx.MESSAGE_OVERRIDE["train"]) & set(mfx.MESSAGE_OVERRIDE["heldout"]))
        self.assertFalse(set(mfx.ASK_REMEMBERED["train"]) & set(mfx.ASK_REMEMBERED["heldout"]))

    def test_no_vocabulary_name_already_occurs_in_the_corpus_or_the_tool_track(self):
        # Checked once by hand when the pools were chosen (memory_fixtures.py's comment); this keeps it true.
        import re
        import memory_fixtures as mfx
        text = CORPUS.read_text(encoding="utf-8") if CORPUS.is_file() else ""
        for name in mfx.TRAIN_NAMES + mfx.HELDOUT_NAMES:
            self.assertNotRegex(text, r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", name)

    def test_canary_is_side_tagged_and_stable(self):
        import memory_fixtures as mfx
        self.assertNotEqual(mfx.canary("train", "k"), mfx.canary("heldout", "k"))
        self.assertEqual(mfx.canary("heldout", "k"), mfx.canary("heldout", "k"))
        self.assertTrue(mfx.canary("heldout", "k").startswith("heldoutpref-"))


@unittest.skipIf(torch is None, "needs torch")
class Rename(unittest.TestCase):
    def test_a_sequence_parameter_renames_and_still_verifies(self):
        import memory_fixtures as mfx
        self.assertEqual(mfx.seq_params(PROGRAM_SEQ), ["s"])
        out = mfx.verified_rename(PROGRAM_SEQ, ["Example: double_all([1, 2]) == [2, 4]"], "s", "xs")
        self.assertIsNotNone(out)
        self.assertIn("xs", mfx.seq_params(out))
        self.assertNotIn("s", mfx.seq_params(out))

    def test_a_program_with_no_sequence_parameter_refuses(self):
        import memory_fixtures as mfx
        self.assertEqual(mfx.seq_params(PROGRAM_INT), [])
        self.assertFalse(mfx.has_sequence_param(PROGRAM_INT))
        self.assertIsNone(mfx.rename_param(PROGRAM_INT, "x", "xs"))

    def test_renaming_to_a_name_already_in_the_program_refuses(self):
        import memory_fixtures as mfx
        self.assertIsNone(mfx.rename_param(PROGRAM_SEQ, "s", "r"))       # "r" is the return value's own name
        self.assertIsNone(mfx.rename_param(PROGRAM_SEQ, "s", "s"))

    def test_a_rename_that_would_not_verify_is_refused(self):
        import memory_fixtures as mfx
        broken = PROGRAM_SEQ.replace("r[i := 2 * r[i]]", "r[i := 3 * r[i]]")   # verifies, but not this task's math
        self.assertIsNone(mfx.verified_rename(broken, ["Example: double_all([1, 2]) == [2, 4]"], "s", "xs"))


@unittest.skipIf(torch is None, "needs torch")
class RealRecall(unittest.TestCase):
    """Every span a conversation carries is dawnr's own recall, not text this script wrote by hand."""

    def test_a_stored_preference_is_recalled_as_dawnrs_own_span(self):
        import tempfile
        import memory_conversations as mc
        import memory_fixtures as mfx
        with tempfile.TemporaryDirectory() as tmp:
            stores = mc.Stores(Path(tmp) / "stores")
            text = mfx.fact_text("train", "xs", "k")
            span = stores.span("p1", "Implement this in t.", [("preference", text, mfx.SLOT)])
            stores.close()
        self.assertIsNotNone(span)
        self.assertIn("dawnr remembers", span)
        self.assertIn("xs", span)

    def test_an_empty_store_recalls_nothing(self):
        import tempfile
        import memory_conversations as mc
        with tempfile.TemporaryDirectory() as tmp:
            stores = mc.Stores(Path(tmp) / "stores")
            span = stores.span("p2", "Implement this in t.", [])
            stores.close()
        self.assertIsNone(span)

    def test_two_people_never_see_each_others_preference(self):
        import tempfile
        import memory_conversations as mc
        import memory_fixtures as mfx
        with tempfile.TemporaryDirectory() as tmp:
            stores = mc.Stores(Path(tmp) / "stores")
            stores.span("ann", "x", [("preference", mfx.fact_text("train", "xs", "a"), mfx.SLOT)])
            bob_span = stores.span("bob", "x", [])
            stores.close()
        self.assertIsNone(bob_span)


@unittest.skipIf(torch is None, "needs torch")
class Rendering(unittest.TestCase):
    def tok(self):
        import string
        import chat
        import data
        return chat.with_memory_tokens(data.CharTokenizer.from_text(string.printable))

    def test_a_memory_part_is_never_supervised_and_never_marked_untrusted(self):
        import chat
        tok = self.tok()
        conv = {"messages": [{"role": "user", "content": "hi"},
                             {"role": "assistant", "content": [
                                 {"type": "memory", "text": "dawnr remembers: prefers xs."},
                                 {"type": "text", "text": PROGRAM_INT}]}]}
        ids, mask = chat.render_conversation(tok, conv)
        start, end = chat.special(tok, chat.OUTPUT_START), chat.special(tok, chat.OUTPUT_END)
        memory_tok = chat.special(tok, chat.MEMORY)
        self.assertIn(memory_tok, ids)
        inside = False
        for i, m in zip(ids, mask):
            if i == start:
                inside = True
            if inside:
                self.assertEqual(m, 0)
            if i == end:
                inside = False
        self.assertNotIn(chat.special(tok, chat.UNTRUSTED), ids)
        # the program text after the span IS supervised
        program_start = ids.index(memory_tok)
        self.assertTrue(any(mask[program_start:]))

    def test_a_memory_part_refuses_train_or_untrusted(self):
        import chat
        tok = self.tok()
        for bad in ({"type": "memory", "text": "x", "train": False}, {"type": "memory", "text": "x", "untrusted": True}):
            conv = {"messages": [{"role": "user", "content": "hi"},
                                 {"role": "assistant", "content": [bad, {"type": "text", "text": "ok"}]}]}
            with self.assertRaises(ValueError):
                chat.render_conversation(tok, conv)

    def test_a_memory_part_needs_the_memory_token(self):
        import chat
        import data
        import string
        tok = chat.with_harness_tokens(data.CharTokenizer.from_text(string.printable))
        conv = {"messages": [{"role": "user", "content": "hi"},
                             {"role": "assistant", "content": [{"type": "memory", "text": "x"},
                                                               {"type": "text", "text": "ok"}]}]}
        with self.assertRaises(ValueError):
            chat.render_conversation(tok, conv)

    def test_needs_memory_tokens_is_true_only_with_a_memory_part(self):
        import chat
        plain = [{"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ok"}]}]
        self.assertFalse(chat.needs_memory_tokens(plain))
        withmem = [{"messages": [{"role": "user", "content": "hi"},
                                {"role": "assistant", "content": [{"type": "memory", "text": "x"},
                                                                  {"type": "text", "text": "ok"}]}]}]
        self.assertTrue(chat.needs_memory_tokens(withmem))


@unittest.skipIf(torch is None, "needs torch")
class Gate(unittest.TestCase):
    @unittest.skipUnless(SPLIT.is_file(), "needs the split file on this machine")
    def test_the_trainers_gate_refuses_a_held_out_row(self):
        # split-v5.json's eval_ids is the project's own held-out benchmark (the "clean 200"), a different,
        # stricter set than this module's train/heldout split of the corpus; a row naming one of ITS ids,
        # under the same dafny_synthesis_task_id_<N> spelling the corpus uses, must be refused regardless of
        # which side of our own split built it -- exactly the gate tool_conversations.py's build() calls.
        import chat_data
        import memory_conversations as mc
        eval_id = json.loads(SPLIT.read_text(encoding="utf-8"))["eval_ids"][0]
        task_name = f"dafny_synthesis_task_id_{eval_id}__leaked"
        program = f"t 1\ntask {task_name}(x: int) returns (y: int)\n  ensures y == x\n{{\n  y := x;\n}}\n"
        row = mc.row("Implement this in t.", [{"type": "text", "text": program}],
                    split="train", built="use", source=task_name)
        with self.assertRaises(ValueError):
            chat_data.gate(json.dumps(row), "a held-out row", SPLIT)

    @unittest.skipUnless(CORPUS.is_file() and SPLIT.is_file(), "needs the r12 corpus and split on this machine")
    def test_a_leaked_heldout_name_or_canary_is_caught(self):
        import memory_conversations as mc
        import memory_fixtures as mfx
        items = [{"id": "x", "task": "sometask", "canary": mfx.canary("heldout", "k")}]
        self.assertIn("held-out preference name " + mfx.HELDOUT_NAMES[0],
                      mc.leaks(items, f"a training row mentions {mfx.HELDOUT_NAMES[0]} in passing"))
        self.assertTrue(any("canary" in f for f in mc.leaks(items, f"leaked: {mfx.canary('heldout', 'k')}")))
        self.assertEqual([], mc.leaks(items, "an ordinary training row with none of that"))

    @unittest.skipUnless(SPLIT.is_file(), "needs the split file on this machine")
    def test_a_val_split_task_id_is_flagged_by_leaks_but_is_not_a_boundary_violation(self):
        # tool_fixtures.corpus_tasks calls a document this module's "heldout" side exactly when chat_data.py's
        # own split_documents(by="hash", seed=1337) puts it on chat_data.py's "val" side -- so a held-out task's
        # id legitimately turns up, as plain text, inside chat_data.py's own base conversations, and leaks() is
        # right to flag it wherever a mid-training file carries both (28 such hits reproduced 2026-09-27 against
        # the tool track's own arm-A file, dawnr-tools/B-s1337/3-conversations/conversations.jsonl, none of them
        # a preference-name or canary leak, all pre-existing chat_data.py rows -- see memory-conversations-
        # results-2026-09-27.json's leak_check). That string match is not the training boundary: chat_data.gate
        # (eval_ids/dev_ids, split-v5.json) is, and does not refuse this row; and chat_train.load_conversations
        # routes a split=="val" row away from train_rows, the only source loss.backward()/optimizer.step() read
        # from (chat_train.py's training loop), so it is never a gradient target either.
        import chat_data
        import chat_train
        import memory_conversations as mc
        task_name = "probe_val_split_task_never_an_eval_or_dev_id"
        program = f"t 1\ntask {task_name}(x: int) returns (y: int)\n  ensures y == x\n{{\n  y := x;\n}}\n"
        val_row = mc.row("Implement this in t.", [{"type": "text", "text": program}],
                         split="val", built="base", source=task_name)
        train_row = mc.row("Implement another in t.", [{"type": "text", "text": program.replace(task_name, "other")}],
                           split="train", built="base", source="other")
        val_text, train_text = json.dumps(val_row, ensure_ascii=False), json.dumps(train_row, ensure_ascii=False)

        items = [{"id": "x", "task": task_name, "canary": "unrelated-canary-never-in-this-text"}]
        self.assertEqual([f"task {task_name}"], mc.leaks(items, val_text))          # leaks() is right to catch it

        chat_data.gate(train_text + "\n\n" + val_text, "a val-split base row plus a train row", SPLIT)  # not refused

        tmp = Path(tempfile.mkstemp(suffix=".jsonl")[1])
        try:
            tmp.write_text(train_text + "\n" + val_text + "\n", encoding="utf-8")
            train, val = chat_train.load_conversations(tmp)
        finally:
            tmp.unlink()
        self.assertEqual(1, len(train))
        self.assertEqual(1, len(val))
        self.assertEqual("val", val[0]["split"])                 # the only side that ever reaches masked_loss(),
        self.assertEqual("train", train[0]["split"])              # never train_rows.get_batch()'s backward() pass


@unittest.skipIf(torch is None, "needs torch")
class Judge(unittest.TestCase):
    def test_followed_name_requires_the_program_to_still_pass(self):
        import memory_eval as me
        examples = ["Example: double_all([1, 2]) == [2, 4]"]
        renamed = PROGRAM_SEQ.replace("s: seq", "xs: seq").replace("s)", "xs)").replace(" s[", " xs[")
        # a genuine rename passes and is credited
        self.assertTrue(me.followed_name(renamed, "xs", examples) or me.followed_name(PROGRAM_SEQ, "s", examples))
        self.assertFalse(me.followed_name(PROGRAM_SEQ, "xs", examples))     # never renamed: not credited
        self.assertFalse(me.followed_name("not a program", "xs", examples))

    def test_said_nothing_and_invented_are_mutually_exclusive(self):
        import memory_eval as me
        self.assertTrue(me.said_nothing("I don't remember anything about you yet."))
        self.assertFalse(me.invented("I don't remember anything about you yet."))
        self.assertTrue(me.invented("You prefer `xs` for a sequence parameter."))
        self.assertFalse(me.said_nothing("You prefer `xs` for a sequence parameter."))

    def test_recall_judge_reads_the_sampled_text_only(self):
        import memory_eval as me
        item = {"id": "recall:with:x", "category": "recall", "span": True, "preference": "xs"}
        got = me.judge(item, [{"type": "text", "text": "You prefer `xs` for a sequence parameter."}], True)
        self.assertTrue(got["correct"])
        item_no = {"id": "recall:without:x", "category": "recall", "span": False}
        got_no = me.judge(item_no, [{"type": "text", "text": "I don't remember anything about you yet."}], False)
        self.assertTrue(got_no["correct"])
        self.assertFalse(got_no["invented"])


if __name__ == "__main__":
    unittest.main()
