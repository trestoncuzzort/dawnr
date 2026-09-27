"""The evals track's report card: memory_metrics.py's arithmetic, dawnr_report.py's scorecard
(reading whatever eval files exist for one checkpoint, "not available" with why for the rest),
injection_eval.py's InjecAgent-shaped rate (a scripted model, since no checkpoint has the
harness tokens trained yet -- this proves the machinery, not a real model's vulnerability),
and checkpoint_bench.py's CPU timing. CPU only. The torch-free classes (Memory, ScorecardPure)
run under a bare interpreter too; the rest needs torch, like the rest of this test family.
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

import memory_metrics as mm  # noqa: E402
import dawnr_report as dr  # noqa: E402


class Memory(unittest.TestCase):
    def test_recall_separates_hallucination_from_false_abstention(self):
        rows = [
            {"person_id": "p1", "probe": "q1", "expected": "blue", "got": "blue",
             "correct": True, "abstained": False},                                   # recalled
            {"person_id": "p1", "probe": "q2", "expected": "red", "got": "I don't have that",
             "correct": False, "abstained": True},                                   # false abstention
            {"person_id": "p1", "probe": "q3", "expected": None, "got": "I don't have that",
             "correct": False, "abstained": True},                                   # correct abstention
            {"person_id": "p1", "probe": "q4", "expected": None, "got": "green (made up)",
             "correct": False, "abstained": False},                                  # hallucination
        ]
        r = mm.recall_metrics(rows)
        self.assertEqual((r["told"], r["untold"]), (2, 2))
        self.assertEqual(r["recall"], 0.5)
        self.assertEqual(r["false_abstention_rate"], 0.5)
        self.assertEqual(r["correct_abstention_rate"], 0.5)
        self.assertEqual(r["hallucinated_on_untold_fact_rate"], 0.5)

    def test_recall_refuses_an_empty_or_malformed_set(self):
        with self.assertRaises(ValueError):
            mm.recall_metrics([])
        with self.assertRaises(ValueError):
            mm.recall_metrics([{"person_id": "p1"}])   # missing every other required key

    def test_personalization_net_positive_needs_both_halves(self):
        rows = [
            {"person_id": "p1", "task": "t1", "with_adapter": 0.8, "without_adapter": 0.5,
             "general_loss_with_adapter": 1.2, "general_loss_baseline": 1.2},   # improved, no regression: net positive
            {"person_id": "p1", "task": "t2", "with_adapter": 0.9, "without_adapter": 0.5,
             "general_loss_with_adapter": 1.5, "general_loss_baseline": 1.2},   # improved, but regressed: not net positive
        ]
        p = mm.personalization_metrics(rows)
        self.assertEqual(p["task_improved_share"], 1.0)
        self.assertEqual(p["general_regressed_share"], 0.5)
        self.assertEqual(p["net_positive_share"], 0.5)

    def test_read_jsonl_missing_file_is_empty_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(mm.read_jsonl(Path(d) / "nope.jsonl"), [])
            f = Path(d) / "r.jsonl"
            f.write_text('{"a": 1}\n\n{"a": 2}\n')     # a blank line must not break parsing
            self.assertEqual(mm.read_jsonl(f), [{"a": 1}, {"a": 2}])


class ScorecardPure(unittest.TestCase):
    """The scorecard's own assembly and rendering: every section absent, then populated, with
    no checkpoint or torch involved -- these sections only ever read files."""

    def test_every_section_not_available_when_nothing_is_given(self):
        data = dr.scorecard(checkpoint=Path("/nowhere"))
        self.assertEqual(data["core_skill"]["dev"]["status"], "not available")
        for name in ("tool_use", "injection", "memory", "personalization", "general_english", "cpu"):
            self.assertEqual(data[name]["status"], "not available", name)
        md = dr.render_scorecard(data)
        self.assertIn("Not available", md)
        json.dumps(data)  # must be JSON-serializable even when every section is absent

    def test_core_skill_and_tool_use_read_chat_eval_files(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            eval_json = d / "eval.json"
            eval_json.write_text(json.dumps({"model": "m", "dev": {
                "asked": 4, "tiers": {"none": 1, "parses": 1, "typed": 1, "tests": 1, "proved-weak": 0, "proved": 0},
                "at_least_typed": 2, "tests_passed": 1, "used_tool": 2, "ended": 4, "proof": "not asked"}}))
            rows_path = d / "eval.rows.jsonl"
            base_row = {"parses": True, "well_formed": True, "examples_all_pass": True, "got_failing_verdict": False,
                        "acted_on_failure": False, "repeated_after_failure": False, "repaired": False,
                        "used_tool": True, "unclosed_call": False, "ended": True, "exact_program": True}
            rows_path.write_text("\n".join(json.dumps(r) for r in [
                {**base_row, "set": "val", "tool": True},
                {**base_row, "set": "val", "tool": True, "examples_all_pass": False, "got_failing_verdict": True},
                {**base_row, "set": "val", "tool": False},          # not in the tool-conversation subset
                {**base_row, "set": "dev", "tool": True},           # not "val": excluded too
            ]) + "\n")
            data = dr.scorecard(checkpoint=d, eval_json=eval_json, eval_rows=rows_path)
            self.assertEqual(data["core_skill"]["dev"]["tests_passed"], 1)
            tu = data["tool_use"]
            self.assertEqual(tu["status"], "ok")
            self.assertEqual(tu["n"], 2)                            # only the two val+tool rows
            self.assertEqual(tu["examples_all_pass"], "1 of 2 (50.0%)")
            md = dr.render_scorecard(data)
            self.assertIn("tests passed: **1 of 4 (25.0%)**", md)
            self.assertIn("2 held-out validation conversations whose proved answer used the tool", md)

    def test_tool_use_not_available_when_rows_file_has_no_tool_true(self):
        with tempfile.TemporaryDirectory() as d:
            rows_path = Path(d) / "eval.rows.jsonl"
            rows_path.write_text(json.dumps({"set": "val", "tool": False, "parses": True}) + "\n")
            section = dr.tool_use_section(rows_path)
            self.assertEqual(section["status"], "not available")
            self.assertIn("no validation row tagged tool: true", section["why"])

    def test_heldout_scores_reports_failure_instead_of_crashing(self):
        # score_heldout.py exits non-zero for a tag with no answer directory at all; heldout_scores
        # must turn that into a reported failure, not an uncaught SystemExit from the subprocess.
        split = dr.ROOT / "t" / "out" / "loop" / "split-v5.json"
        if not split.exists():
            self.skipTest(f"{split} not present in this checkout")
        result = dr.heldout_scores("no-such-tag-ever-2026-09-27", split)
        self.assertFalse(result["ok"])
        self.assertNotEqual(result["returncode"], 0)

    def test_injection_memory_personalization_general_english_cpu_sections_read_json(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            inj = d / "injection.json"
            inj.write_text(json.dumps({"model": "m", "fixtures": 9, "followed": 2, "injection_following_rate": 0.2222,
                                       "used_the_vector_tool": 9, "by_disguise": {"plain": {"n": 3, "followed": 1,
                                                                                            "rate": 0.3333}},
                                       "rows": [{"huge": "dropped from the section"}]}))
            self.assertEqual(dr.injection_section(inj)["fixtures"], 9)
            self.assertNotIn("rows", dr.injection_section(inj))       # the raw per-fixture rows stay in the file only

            mem = d / "memory.jsonl"
            mem.write_text(json.dumps({"person_id": "p1", "probe": "q", "expected": "x", "got": "x",
                                       "correct": True, "abstained": False}) + "\n")
            self.assertEqual(dr.memory_section(mem)["recall"], 1.0)
            self.assertEqual(dr.memory_section(d / "missing.jsonl")["status"], "not available")

            pers = d / "pers.jsonl"
            pers.write_text(json.dumps({"person_id": "p1", "task": "t", "with_adapter": 0.9, "without_adapter": 0.5,
                                        "general_loss_with_adapter": 1.0, "general_loss_baseline": 1.0}) + "\n")
            self.assertEqual(dr.personalization_section(pers)["net_positive_share"], 1.0)

            ge = d / "english.json"
            ge.write_text(json.dumps({"shard": "s", "documents": 3, "nats_per_token": 1.5, "nats_per_char": 0.4}))
            self.assertEqual(dr.general_english_section(ge)["nats_per_token"], 1.5)

            cpu = d / "cpu.json"
            cpu.write_text(json.dumps({"parameters": 1000, "processor": "x", "threads": 4,
                                       "median_tokens_per_second": 12.5, "median_ms_per_token": 80.0,
                                       "peak_rss_bytes": 2**20, "runs": [{"dropped": True}]}))
            section = dr.cpu_section(cpu)
            self.assertEqual(section["parameters"], 1000)
            self.assertNotIn("runs", section)

            data = dr.scorecard(checkpoint=d, injection_json=inj, memory_jsonl=mem, personalization_jsonl=pers,
                                english_json=ge, cpu_json=cpu)
            md = dr.render_scorecard(data)
            for needle in ("InjecAgent-shaped, arXiv:2403.02691", "LongMemEval-shaped, arXiv:2410.10813",
                          "mean task uplift", "nats/token", "tok/s"):
                self.assertIn(needle, md)

    def test_write_scorecard_writes_both_files_and_json_matches_markdown_source(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            md_path, json_path = dr.write_scorecard(out, checkpoint=Path(d) / "ckpt")
            self.assertTrue(md_path.exists() and json_path.exists())
            data = json.loads(json_path.read_text())
            self.assertEqual(dr.render_scorecard(data), md_path.read_text())

    def test_pipeline_run_report_unchanged_by_the_scorecard_additions(self):
        """The exact scenario test_dawnr_chat.py's Driver.test_report_reads_stage_records
        checks: build()/write() must still behave byte-for-byte as before this track's work."""
        import dawnr_pipeline as dp
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
            text = dr.build(d)
        self.assertIn("2.5000 on the train side", text)
        self.assertIn("tests passed: **1 of 4 (25.0%)**", text)
        self.assertIn("| mid | not run |", text)
        self.assertIn("skipped: no data", text)
        self.assertIn("Not scored", text)

    def test_cli_run_mode_rejects_checkpoint_only_flags(self):
        with self.assertRaises(SystemExit):
            dr.main(["--run", "/nowhere", "--cpu-json", "/nowhere/cpu.json"])


import torch  # noqa: E402

import chat  # noqa: E402
import chat_data  # noqa: E402
import data  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402


def char_tok(extra: str = ""):
    return data.CharTokenizer.from_text(string.printable + extra)


def save_checkpoint(path: Path, model, tok) -> None:
    path.mkdir(parents=True, exist_ok=True)
    torch.save({"model": model.state_dict(), "config": model.config.__dict__,
                "tokenizer_fingerprint": data.tokenizer_fingerprint(tok)}, path / "ckpt.pt")
    tok.save(path / "tokenizer.json")


class ScriptedInjectionModel(torch.nn.Module):
    """Walks a fixed list of tool calls, one per <|tool_start|>...<|tool_end|> span, driven only
    by its own position -- ScriptedModel's pattern in test_dawnr_chat.py, generalised to more
    than one call. Proves run_fixtures()/followed()/injection_rate() wire together correctly;
    it is not a measurement of a real model, which needs a harness-token checkpoint that does
    not exist yet (injection_eval.py's own module docstring)."""

    def __init__(self, tok, calls: list[str], block=8192):
        super().__init__()
        self.w = torch.nn.Parameter(torch.zeros(1))
        self.config = GPTConfig(vocab_size=tok.vocab_size, block_size=block, n_layer=1, n_head=1, n_embd=4)
        self.tok, self.calls, self.call_i, self.pos = tok, calls, 0, None

    def forward_cached(self, idx, cache=None, *, only_last=False):
        sp = lambda n: chat.special(self.tok, n)                         # noqa: E731
        last = int(idx[0, -1])
        ids = self.tok.encode(self.calls[self.call_i]) if self.call_i < len(self.calls) else None
        if last in (sp(chat.ASSISTANT_START), sp(chat.OUTPUT_END)):
            nxt = sp(chat.TOOL_START) if ids is not None else sp(chat.ASSISTANT_END)
        elif last == sp(chat.TOOL_START):
            self.pos = 0
            nxt = ids[0]
        elif self.pos is not None and self.pos < len(ids) - 1:
            self.pos += 1
            nxt = ids[self.pos]
        elif self.pos is not None:
            self.pos = None
            self.call_i += 1
            nxt = sp(chat.TOOL_END)
        else:
            nxt = 0
        logits = torch.full((idx.size(0), 1, self.tok.vocab_size), -1e9)
        logits[:, :, nxt] = 0.0
        return logits, ()


class InjectionEvalTest(unittest.TestCase):
    def setUp(self):
        import injection_eval as ie
        self.ie = ie
        self.tok = chat.with_harness_tokens(char_tok())
        self.fixtures = ie.load_fixtures()
        self.assertTrue(self.tok.sentinel_id(chat.UNTRUSTED) >= 0)  # the token this whole track depends on exists

    def test_a_vulnerable_model_is_scored_followed(self):
        from dawnr_harness.tools import format_call
        from engine import Engine
        fx = self.fixtures[0]
        target_text = format_call(fx["target_call"]["name"], fx["target_call"]["arguments"])
        model = ScriptedInjectionModel(self.tok, ["read_page {\"url\": \"https://example.org\"}", target_text])
        harness, fixture_output = self.ie.build_fixture_harness()
        engine = Engine(model, self.tok, harness=harness)
        rows = self.ie.run_fixtures(engine, self.tok, harness, fixture_output, [fx], max_tokens=400)
        self.assertTrue(rows[0]["followed"], rows[0])
        self.assertTrue(rows[0]["used_read_page"])
        rate = self.ie.injection_rate(rows)
        self.assertEqual(rate["injection_following_rate"], 1.0)

    def test_a_safe_model_that_only_reads_the_page_is_scored_not_followed(self):
        from engine import Engine
        fx = self.fixtures[0]
        model = ScriptedInjectionModel(self.tok, ["read_page {\"url\": \"https://example.org\"}"])
        harness, fixture_output = self.ie.build_fixture_harness()
        engine = Engine(model, self.tok, harness=harness)
        rows = self.ie.run_fixtures(engine, self.tok, harness, fixture_output, [fx], max_tokens=400)
        self.assertFalse(rows[0]["followed"], rows[0])
        self.assertTrue(rows[0]["used_read_page"])
        self.assertEqual(self.ie.injection_rate(rows)["injection_following_rate"], 0.0)

    def test_a_call_to_a_different_tool_with_different_arguments_is_not_followed(self):
        """followed() must not credit a coincidental call to the target tool with unrelated
        arguments -- the fixture names one exact call because that is what the injected text
        asked for, not merely a tool the reply happens to reach for."""
        from engine import Engine
        fx = self.fixtures[0]
        other_args = dict(fx["target_call"]["arguments"], to="someone-else@example.org")
        from dawnr_harness.tools import format_call
        near_miss = format_call(fx["target_call"]["name"], other_args)
        model = ScriptedInjectionModel(self.tok, ["read_page {\"url\": \"https://example.org\"}", near_miss])
        harness, fixture_output = self.ie.build_fixture_harness()
        engine = Engine(model, self.tok, harness=harness)
        rows = self.ie.run_fixtures(engine, self.tok, harness, fixture_output, [fx], max_tokens=400)
        self.assertFalse(rows[0]["followed"], rows[0])

    def test_main_refuses_a_checkpoint_with_no_harness_tokens(self):
        chat_only_tok = chat.with_chat_tokens(char_tok())
        model = GPT(GPTConfig(vocab_size=chat_only_tok.vocab_size, block_size=64, n_layer=1, n_head=1, n_embd=8))
        with tempfile.TemporaryDirectory() as d:
            ckpt = Path(d) / "ckpt"
            save_checkpoint(ckpt, model, chat_only_tok)
            with self.assertRaises(SystemExit):
                self.ie.main(["--model", str(ckpt), "--out", str(Path(d) / "out.json")])

    def test_fixtures_cover_every_owasp_disguise_named_in_dawnr_harness_md(self):
        self.assertEqual({f["disguise"] for f in self.fixtures}, {"plain", "encoded", "split", "typo"})
        for fx in self.fixtures:
            for key in ("id", "user", "untrusted_output", "target_call", "disguise"):
                self.assertIn(key, fx)


class CheckpointBenchTest(unittest.TestCase):
    def test_run_reports_positive_throughput_and_peak_memory_for_a_tiny_checkpoint(self):
        import checkpoint_bench as cb
        tok = char_tok()
        model = GPT(GPTConfig(vocab_size=tok.vocab_size, block_size=64, n_layer=1, n_head=1, n_embd=8))
        with tempfile.TemporaryDirectory() as d:
            ckpt = Path(d) / "ckpt"
            save_checkpoint(ckpt, model, tok)
            result = cb.run(ckpt, "function to ", tokens=4, repeats=2, threads=1)
        self.assertEqual(len(result["runs"]), 2)
        self.assertGreater(result["median_tokens_per_second"], 0)
        self.assertGreater(result["peak_rss_bytes"], 0)
        self.assertEqual(result["parameters"], model.total_params())
        self.assertEqual(result["threads"], 1)

    def test_cli_writes_json_without_the_per_repeat_rows_in_the_printed_summary(self):
        import checkpoint_bench as cb
        tok = char_tok()
        model = GPT(GPTConfig(vocab_size=tok.vocab_size, block_size=64, n_layer=1, n_head=1, n_embd=8))
        with tempfile.TemporaryDirectory() as d:
            ckpt = Path(d) / "ckpt"
            save_checkpoint(ckpt, model, tok)
            out = Path(d) / "bench.json"
            self.assertEqual(cb.main(["--model", str(ckpt), "--out", str(out), "--tokens", "4", "--repeats", "1"]), 0)
            data = json.loads(out.read_text())
        self.assertIn("runs", data)
        self.assertGreater(data["peak_rss_bytes"], 0)


class GeneralEnglishTest(unittest.TestCase):
    def test_english_loss_from_shard_reuses_dawnr_pipeline_heldout_loss(self):
        tok = char_tok()
        model = GPT(GPTConfig(vocab_size=tok.vocab_size, block_size=64, n_layer=1, n_head=2, n_embd=16))
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ckpt = d / "ckpt"
            save_checkpoint(ckpt, model, tok)
            shard = d / "shard.txt"
            shard.write_text("The quick fox runs.\n\nA second held-out document follows here.\n\n")
            result = dr.english_loss_from_shard(ckpt, shard)
        self.assertEqual(result["documents"], 2)
        self.assertEqual(result["shard"], str(shard))
        self.assertTrue(result["nats_per_token"] > 0)

    def test_general_english_section_reads_back_a_written_result(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "english.json"
            path.write_text(json.dumps({"shard": "s.txt", "documents": 2, "nats_per_token": 1.23, "nats_per_char": 0.3}))
            section = dr.general_english_section(path)
        self.assertEqual(section["status"], "ok")
        self.assertEqual(section["documents"], 2)


if __name__ == "__main__":
    unittest.main()
