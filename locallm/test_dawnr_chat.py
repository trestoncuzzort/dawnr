"""dawnr's chat pipeline: tokens, masking, the t tool, conversations, engine, trainer, driver, report.

What must hold: the chat tokens sit past the vocabulary where no text reaches
them and leave ordinary and FIM ids alone; the mask supervises exactly the
assistant's text, its tool calls and <|assistant_end|>, never the user or the
tool's output (nanochat's rule); a conversation over the block is refused, not
cut; growing the embedding leaves every old logit unchanged; the t tool's
verdicts are the interpreter's and keep true apart from 1; examples computed
from a proved program pass that program; conversations follow the hash split
and a corpus naming a held-out id is refused; the engine runs the tool on the
program between the tool tokens, forces its answer back with mask 0, and
matches plain greedy decoding elsewhere; a tiny CPU chat run trains, saves a
checkpoint load_checkpoint reads, resumes only on identical inputs; the
driver skips a stage only for identical inputs; the report reads what stages
wrote. Needs torch; CPU only, seconds.
"""
import json
import string
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "t"))

import torch  # noqa: E402

import chat  # noqa: E402
import chat_data  # noqa: E402
import data  # noqa: E402
import fim  # noqa: E402
import t_tool  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402

PROGRAM = """t 1
task double(x: int) returns (y: int)
  requires x >= 0
  ensures y == 2 * x
{
  y := 2 * x;
}
"""
HEADED = "Problem: Double a number\nSignature: double(int) -> int\n" + PROGRAM
SPLIT = HERE.parent / "t" / "out" / "loop" / "split-v5.json"


def char_tok(extra: str = ""):
    # every printable character: a character tokenizer drops what it never saw,
    # the tool's own words included
    return data.CharTokenizer.from_text(string.printable + extra)


def conv(user="Double it", answer="y := 2 * x;", tool_output=None):
    content = answer if tool_output is None else [{"type": "t", "text": answer},
                                                   {"type": "t_output", "text": tool_output}]
    return {"messages": [{"role": "user", "content": user}, {"role": "assistant", "content": content}]}


class Tokens(unittest.TestCase):
    def test_past_the_vocabulary_and_unreachable_from_text(self):
        base = char_tok("<|>_")
        tok = chat.with_chat_tokens(base)
        self.assertEqual(tok.vocab_size, base.vocab_size + len(chat.CHAT_TOKENS))
        for name in chat.CHAT_TOKENS:
            self.assertGreaterEqual(chat.special(tok, name), base.vocab_size)
        spelled = tok.encode("<|user_start|> <|t_start|>")
        self.assertTrue(all(i < base.vocab_size for i in spelled))
        self.assertEqual(tok.encode(PROGRAM), base.encode(PROGRAM))

    def test_fim_ids_kept_and_both_sets_present(self):
        tok = chat.with_chat_tokens(char_tok().with_sentinels(fim.SENTINELS))
        self.assertEqual(tok.sentinels[:4], fim.SENTINELS)
        self.assertTrue(chat.has_chat_tokens(tok))
        self.assertIs(chat.with_chat_tokens(tok), tok)

    def test_save_load_round_trip(self):
        tok = chat.with_chat_tokens(char_tok())
        with tempfile.TemporaryDirectory() as d:
            tok.save(Path(d) / "tokenizer.json")
            back = data.load_tokenizer(Path(d) / "tokenizer.json")
        self.assertEqual(data.tokenizer_fingerprint(back), data.tokenizer_fingerprint(tok))
        self.assertEqual(chat.special(back, chat.T_END), chat.special(tok, chat.T_END))


class Rendering(unittest.TestCase):
    def setUp(self):
        self.tok = chat.with_chat_tokens(char_tok())

    def test_mask_is_nanochats(self):
        c = conv(answer="y := 2;", tool_output="parses: yes")
        ids, mask = chat.render_conversation(self.tok, c)
        sp = lambda n: chat.special(self.tok, n)                         # noqa: E731
        by = dict(zip(ids, mask))
        for name, want in ((chat.USER_START, 0), (chat.USER_END, 0), (chat.ASSISTANT_START, 0),
                           (chat.T_START, 1), (chat.T_END, 1), (chat.OUTPUT_START, 0), (chat.OUTPUT_END, 0),
                           (chat.ASSISTANT_END, 1)):
            self.assertEqual(by[sp(name)], want, name)
        # the user's text and the tool's text are unsupervised, the call's text supervised
        text = self.tok.decode([i for i, m in zip(ids, mask) if m and i < 10 ** 6
                                and i not in {sp(n) for n in chat.CHAT_TOKENS}])
        self.assertEqual(text, "y := 2;")

    def test_system_refused_and_completion_primed(self):
        with self.assertRaises(ValueError):
            chat.render_conversation(self.tok, {"messages": [{"role": "system", "content": "x"}]})
        ids = chat.render_for_completion(self.tok, conv())
        self.assertEqual(ids[-1], chat.special(self.tok, chat.ASSISTANT_START))
        self.assertNotIn(chat.special(self.tok, chat.ASSISTANT_END), ids)

    def test_final_program(self):
        self.assertEqual(chat.final_program([{"type": "t", "text": "a"}, {"type": "t_output", "text": "o"},
                                             {"type": "t", "text": " b "}]), "b")
        self.assertEqual(chat.final_program(" p "), "p")

    def test_batches_mask_targets_and_refuse_over_block(self):
        c = conv(tool_output="parses: yes")
        ids, mask = chat.render_conversation(self.tok, c)
        rows = chat.ConversationBatches([c], self.tok, len(ids) + 5, seed=1)
        y = rows.y[0].tolist()
        for t in range(len(ids) - 1):
            self.assertEqual(y[t], ids[t + 1] if mask[t + 1] else chat.IGNORE_INDEX)
        self.assertTrue(all(v == chat.IGNORE_INDEX for v in y[len(ids) - 1:]))
        self.assertEqual(rows.record()["tool_calls"], 1)
        with self.assertRaises(ValueError):
            chat.ConversationBatches([c], self.tok, len(ids) - 3, seed=1)
        a, b = chat.ConversationBatches([c, conv()], self.tok, 200, 7), chat.ConversationBatches([c, conv()], self.tok, 200, 7)
        self.assertTrue(torch.equal(a.get_batch(3, 1)[0], b.get_batch(3, 1)[0]))


class Growth(unittest.TestCase):
    def test_old_logits_unchanged(self):
        torch.manual_seed(0)
        base = char_tok()
        model = GPT(GPTConfig(vocab_size=base.vocab_size, block_size=32, n_layer=1, n_head=2, n_embd=16)).eval()
        x = torch.tensor([base.encode("y := 2")])
        before, _ = model(x)
        tok = chat.with_chat_tokens(base)
        self.assertEqual(chat.grow_embeddings(model, tok.vocab_size), len(chat.CHAT_TOKENS))
        after, _ = model(x)
        self.assertTrue(torch.allclose(before, after[..., :base.vocab_size], atol=1e-6))
        self.assertIs(model.transformer.wte.weight, model.lm_head.weight)
        self.assertTrue(torch.allclose(model.lm_head.weight[-1], model.lm_head.weight[:base.vocab_size].mean(0)))


class Tool(unittest.TestCase):
    def test_verdicts(self):
        out = t_tool.call(PROGRAM, "Example: double(3) == 6\nExample: double(4) == 9\nExample: double(-1) == -2")
        self.assertEqual(out.split("\n"), ["parses: yes", "well formed: yes", "example 1: pass",
                                           "example 2: fail: got 8, expected 9", "example 3: requires-excluded"])
        self.assertTrue(t_tool.call("t 1\ntask f(x: int) returns (y: int) {", "").startswith("parses: no"))
        bad = PROGRAM.replace("y := 2 * x;", "y := z;")
        self.assertIn("well formed: no", t_tool.call(bad, ""))

    def test_bool_is_not_one(self):
        prog = "t 1\ntask pos(x: int) returns (b: bool)\n  ensures b == (x > 0)\n{\n  b := x > 0;\n}\n"
        self.assertIn("example 1: fail", t_tool.call(prog, "Example: pos(3) == 1"))
        self.assertIn("example 1: pass", t_tool.call(prog, "Example: pos(3) == true"))

    def test_examples_from_program_pass_it(self):
        lines = t_tool.examples_from_program(PROGRAM)
        self.assertEqual(len(lines), 2)
        out = t_tool.call(PROGRAM, "\n".join(lines))
        self.assertEqual(out.count(": pass"), 2, out)


class Conversations(unittest.TestCase):
    def test_headed_and_spec_prompts(self):
        c = chat_data.conversation(HEADED, tool=False)
        self.assertEqual(c["kind"], "problem")
        self.assertTrue(c["messages"][0]["content"].startswith("Problem: Double a number\nSignature:"))
        self.assertEqual(c["messages"][1]["content"], PROGRAM)
        s = chat_data.conversation(PROGRAM, tool=True)
        self.assertEqual(s["kind"], "spec")
        user = s["messages"][0]["content"]
        self.assertIn("ensures y == 2 * x", user)
        self.assertNotIn("y := 2 * x;", user)                  # the body is the answer, not the prompt
        parts = s["messages"][1]["content"]
        self.assertEqual([p["type"] for p in parts], ["t", "t_output"])
        self.assertEqual(parts[1]["text"], t_tool.call(PROGRAM, user))

    def test_split_follows_the_hash_split_and_tool_choice_is_stable(self):
        other = PROGRAM.replace("double", "twice")
        text = HEADED + "\n\n\n" + other
        rows, summary = chat_data.build(text, split_seed=3, val_frac=0.5, tool_rate=0.5)
        train, val = data.split_documents(text, val_frac=0.5, seed=3, by="hash")
        self.assertEqual(summary["train"], len(train))
        self.assertEqual(summary["val"], len(val))
        self.assertEqual(chat_data.uses_tool(other, 0, 0.5), chat_data.uses_tool("\n" + other + "\n", 0, 0.5))

    def test_held_out_id_refused(self):
        held = sorted(json.loads(SPLIT.read_text())["eval_ids"])[0]
        leaked = PROGRAM.replace("double", f"mbpp_{held}__double")
        with self.assertRaises(ValueError):
            chat_data.gate(leaked, "test", SPLIT)
        chat_data.gate(PROGRAM, "test", SPLIT)


class ScriptedModel(torch.nn.Module):
    """Emits <|t_start|> program <|t_end|>, then <|assistant_end|> once the tool's answer has been read."""

    def __init__(self, tok, program, block=4096):
        super().__init__()
        self.w = torch.nn.Parameter(torch.zeros(1))
        self.config = GPTConfig(vocab_size=tok.vocab_size, block_size=block, n_layer=1, n_head=1, n_embd=4)
        self.tok, self.program, self.pos = tok, tok.encode(program), None

    def forward_cached(self, idx, cache=None, *, only_last=False):
        sp = lambda n: chat.special(self.tok, n)                         # noqa: E731
        last = int(idx[0, -1])
        if last == sp(chat.ASSISTANT_START):
            nxt = sp(chat.T_START)
        elif last == sp(chat.T_START):
            self.pos = 0
            nxt = self.program[0]
        elif self.pos is not None and self.pos < len(self.program) - 1:
            self.pos += 1
            nxt = self.program[self.pos]
        elif self.pos is not None:
            self.pos = None
            nxt = sp(chat.T_END)
        elif last == sp(chat.OUTPUT_END):
            nxt = sp(chat.ASSISTANT_END)
        else:
            nxt = 0
        logits = torch.full((idx.size(0), 1, self.tok.vocab_size), -1e9)
        logits[:, :, nxt] = 0.0
        return logits, ()


class EngineTests(unittest.TestCase):
    def test_tool_runs_and_its_answer_is_forced_with_mask_0(self):
        from engine import Engine, reply_parts
        tok = chat.with_chat_tokens(char_tok())
        user = "Example: double(3) == 6"
        seen = []

        def tool(program, context):
            seen.append((program, context))
            return t_tool.call(program, context)
        eng = Engine(ScriptedModel(tok, PROGRAM), tok, tool=tool)
        prompt = chat.render_for_completion(tok, {"messages": [{"role": "user", "content": user}]})
        results, masks = eng.generate_batch(prompt, 1, max_tokens=500, temperature=0.0)
        self.assertEqual(seen[0][0], PROGRAM)
        self.assertIn(user, seen[0][1])
        parts = reply_parts(tok, results[0])
        self.assertEqual(parts, [{"type": "t", "text": PROGRAM},
                                 {"type": "t_output", "text": t_tool.call(PROGRAM, user)}])
        out_start = results[0].index(chat.special(tok, chat.OUTPUT_START))
        out_end = results[0].index(chat.special(tok, chat.OUTPUT_END))
        self.assertTrue(all(m == 0 for m in masks[0][out_start:out_end + 1]))
        self.assertTrue(all(m == 1 for m in masks[0][:out_start]))
        self.assertTrue(eng.rows[0].completed)
        self.assertEqual(len(eng.rows[0].tool_calls), 1)

    def test_greedy_matches_plain_generation_until_a_chat_token(self):
        from engine import Engine
        torch.manual_seed(0)
        tok = chat.with_chat_tokens(char_tok())
        model = GPT(GPTConfig(vocab_size=tok.vocab_size, block_size=64, n_layer=2, n_head=2, n_embd=16)).eval()
        prompt = tok.encode("y := 2 * x")
        want = model.generate(torch.tensor([prompt]), 20, temperature=0.0)[0, len(prompt):].tolist()
        eng = Engine(model, tok, tool=lambda p, c: "")
        rows = [col for col, _ in eng.generate(prompt, num_samples=2, max_tokens=20, temperature=0.0)]
        got0 = [c[0] for c in rows]
        self.assertEqual([c[0] for c in rows], [c[1] for c in rows])          # the cache copied to both rows
        n = next((i for i, t in enumerate(want) if t >= tok.vocab_size - len(chat.CHAT_TOKENS)), len(want))
        self.assertEqual(got0[:n], want[:n])


class Trainer(unittest.TestCase):
    def test_tiny_cpu_run_saves_loads_and_resumes_only_on_same_inputs(self):
        import chat_train
        from checkpoint import load_checkpoint
        tok = char_tok()
        torch.manual_seed(0)
        model = GPT(GPTConfig(vocab_size=tok.vocab_size, block_size=512, n_layer=1, n_head=2, n_embd=16))
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            init = d / "init"
            init.mkdir()
            torch.save({"model": model.state_dict(), "config": model.config.__dict__,
                        "tokenizer_fingerprint": data.tokenizer_fingerprint(tok)}, init / "ckpt.pt")
            tok.save(init / "tokenizer.json")
            rows = [dict(chat_data.conversation(HEADED, tool=True), split="train"),
                    dict(chat_data.conversation(PROGRAM, tool=False), split="val")]
            convs = d / "c.jsonl"
            convs.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            out = d / "out"
            args = ["--init", str(init), "--conversations", str(convs), "--out", str(out), "--steps", "4",
                    "--batch-size", "1", "--eval-every", "2", "--device", "cpu", "--lr", "1e-2", "--warmup", "1"]
            self.assertEqual(chat_train.main(args), 0)
            run = json.loads((out / "run.json").read_text())
            self.assertEqual(run["status"], "complete")
            self.assertEqual(run["identities"]["chat_tokens_added"], len(chat.CHAT_TOKENS))
            self.assertLess(run["final"]["train"], run["initial"]["train"])
            m, t, cfg = load_checkpoint(out, "cpu")
            self.assertTrue(chat.has_chat_tokens(t))
            self.assertEqual(cfg.vocab_size, tok.vocab_size + len(chat.CHAT_TOKENS))
            self.assertEqual(chat_train.main(args + ["--resume"]), 0)            # same inputs: resumes at the end
            convs.write_text("\n".join(json.dumps(r) for r in rows[:1] + rows) + "\n")
            with self.assertRaises(SystemExit):
                chat_train.main(args + ["--resume"])


class Driver(unittest.TestCase):
    def test_stage_skips_only_for_identical_inputs(self):
        import dawnr_pipeline as dp
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            f = d / "in.txt"
            f.write_text("a")
            st = dp.Stage(d, 1, "x")
            fp = dp.fingerprint({"file": f, "n": 1})
            self.assertFalse(st.done_for(fp))
            st.write("running", fp)
            self.assertTrue(st.interrupted_for(fp))
            self.assertFalse(st.done_for(fp))
            st.write("done", fp)
            self.assertTrue(st.done_for(dp.fingerprint({"file": f, "n": 1})))
            f.write_text("b")
            self.assertFalse(st.done_for(dp.fingerprint({"file": f, "n": 1})))
            self.assertFalse(st.done_for(dp.fingerprint({"file": f, "n": 2})))

    def test_report_reads_stage_records(self):
        import dawnr_pipeline as dp
        import dawnr_report
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            dp.Stage(d, 1, "tokenizer").write("done", {}, seconds=0.1, result={
                "origin": "core", "vocab_size": 10, "fingerprint": "f", "chars_per_token_train": 2.5,
                "chars_per_token_val": 2.25, "train_documents": 9, "val_documents": 1})
            dp.Stage(d, 6, "rl").write("skipped", {}, seconds=0.0, result={"why": "no data"})
            dp.Stage(d, 7, "eval").write("done", {}, seconds=1.0, result={
                "dev": {"asked": 4, "tiers": {"none": 1, "parses": 1, "typed": 1, "tests": 1, "proved-weak": 0,
                                              "proved": 0}, "at_least_typed": 2, "tests_passed": 1,
                        "used_tool": 2, "ended": 4, "proof": "not asked"}, "rows": "r"})
            text = dawnr_report.build(d)
        self.assertIn("2.5000 on the train side", text)
        self.assertIn("tests passed: **1 of 4 (25.0%)**", text)
        self.assertIn("| mid | not run |", text)
        self.assertIn("skipped: no data", text)
        self.assertIn("Not scored", text)


if __name__ == "__main__":
    unittest.main()
