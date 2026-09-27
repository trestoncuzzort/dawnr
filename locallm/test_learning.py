"""dawnr's per-person learning: feedback, synthetic persons, LoRA adapters, the sleep step (DAWNR-LEARNING.md).

What must hold. The store keeps every answer with its feedback, a person can
read, correct, export and erase it, and erasing keeps only an id and a time;
outside content and targets that fail the t tool never become training
examples; the "that's wrong" detector fires on verdicts and not on questions.
Each synthetic person's rewrite is capture-free, leaves the parse tree alone
where it claims to, passes the t tool, and is a fixed point (a person does not
edit their own answer). A LoRA adapter starts exactly at the base, switches
off to the base, comes off leaving the base bit for bit, merges to the same
function, saves and loads, and refuses a model it was not made for. A sleep
trains only the adapter (the base's fingerprint is unchanged), lowers the
person's loss, keeps the best weights, is refused by the guard when it makes
held-out plain text worse than allowed, and an adapter goes stale when an
example it learned from is erased.

The first two groups need only the standard library; the rest need torch and
run on the CPU in seconds.
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

from dawnr_learning import feedback as F  # noqa: E402
from dawnr_learning import persons as P  # noqa: E402

SPLIT = HERE.parent / "t" / "out" / "loop" / "split-v5.json"

PROGRAM = """t 1
gate loops
task count_up(n: int) returns (s: int)
  requires n >= 0
  ensures s == n * (n + 1) / 2
{
  var i_v: int := 0;
  s := 0;
  while i_v != n
    invariant 0 <= i_v and i_v <= n
    invariant s == i_v * (i_v + 1) / 2
    decreases if i_v <= n then n - i_v else i_v - n
  {
    i_v := i_v + 1;
    s := s + i_v;
  }
}
"""
USER = "Implement this specification in t.\nExample: count_up(3) == 6\nExample: count_up(4) == 10"

BRANCHY = """t 1
task pick(x: int) returns (r: int)
  ensures r >= 0
  ensures r == x or r == -x
{
  var i: int := 0;
  if x < 0 {
    r := -x;
  } else {
    r := x;
  }
  i := r;
}
"""
BRANCHY_USER = "Implement this.\nExample: pick(-3) == 3\nExample: pick(5) == 5"

SHADOWED = """t 1
gate quantifiers
task all_pos(s: seq) returns (r: bool)
  ensures r == (forall i in [0, len(s)) . s[i] > 0)
{
  r := true;
  var i: int := 0;
  while i < len(s)
    invariant r == (forall j in [0, i) . j < len(s) ==> s[j] > 0)
    invariant i >= 0
    decreases len(s) - i
  {
    if s[i] <= 0 {
      r := false;
    } else {
    }
    i := i + 1;
  }
}
"""
SHADOWED_USER = "Implement this.\nExample: all_pos([1, 2]) == true\nExample: all_pos([1, -2]) == false"


def store(tmp) -> F.PersonStore:
    return F.PersonStore("Tester", root=tmp)


# ------------------------------------------------------------------ store --

class Store(unittest.TestCase):
    def test_person_names_are_safe_folder_names(self):
        self.assertEqual(F.person_id("Ada"), "ada")
        for bad in ("", "../x", "a/b", "x" * 65, "sp ace", ".hidden"):
            with self.assertRaises(ValueError):
                F.person_id(bad)

    def test_answer_feedback_and_training_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = store(tmp)
            msgs = [{"role": "user", "content": USER}]
            up = s.add_answer(msgs, PROGRAM, session="one")
            down = s.add_answer(msgs, "no idea", session="one")
            edited = s.add_answer(msgs, "t 1\ntask broken", session="one")
            wrong_bare = s.add_answer(msgs, PROGRAM.replace("s + i_v", "s - i_v"), session="one")
            wrong_fixed = s.add_answer(msgs, PROGRAM.replace("s + i_v", "s - i_v"), session="two")
            unrated = s.add_answer(msgs, PROGRAM, session="two")
            s.rate(up, True)
            s.rate(down, False)
            s.edit(edited, PROGRAM)
            s.wrong(wrong_bare, note="that's wrong")
            s.wrong(wrong_fixed, note="that's wrong", correction=PROGRAM)
            examples, excluded = s.training_examples()
            self.assertEqual(sorted(e["id"] for e in examples), sorted([up, edited, wrong_fixed]))
            self.assertEqual(excluded, {"no target": 2, "no feedback": 1})
            self.assertTrue(all(e["messages"][-1] == {"role": "assistant", "content": PROGRAM} for e in examples))
            summary = s.summary()
            self.assertEqual((summary["up"], summary["down"], summary["edit"], summary["wrong"], summary["unrated"]),
                             (1, 1, 1, 2, 1))
            self.assertEqual(summary["sessions"], 2)
            del unrated

    def test_failing_targets_and_outside_content_are_not_trained_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = store(tmp)
            msgs = [{"role": "user", "content": USER}]
            bad = s.add_answer(msgs, PROGRAM)
            s.edit(bad, PROGRAM.replace("s + i_v", "s + 1"))            # fails the examples
            outside = s.add_answer(msgs, [{"type": "tool", "text": "web_fetch {}"},
                                          {"type": "tool_output", "text": "page", "untrusted": True},
                                          {"type": "text", "text": PROGRAM}])
            s.rate(outside, True)
            examples, excluded = s.training_examples()
            self.assertEqual(examples, [])
            self.assertEqual(excluded, {"target fails the t tool": 1, "untrusted content": 1})

    def test_read_correct_export_erase(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = store(tmp)
            msgs = [{"role": "user", "content": USER}]
            a = s.add_answer(msgs, PROGRAM)
            b = s.add_answer(msgs, PROGRAM)
            s.rate(a, True)
            s.rate(b, True)
            before = s.current_hashes()
            s.correct(a, PROGRAM.replace("i_v", "k"))
            self.assertNotEqual(before[a], s.current_hashes()[a])
            self.assertEqual(before[b], s.current_hashes()[b])
            s.erase(b)
            self.assertEqual([r["id"] for r in s.records()], [a])
            exported = s.export()
            self.assertEqual([t["id"] for t in exported["erased"]], [b])
            self.assertNotIn(PROGRAM.split("\n")[2], json.dumps(exported["erased"]))   # no content in a tombstone
            with self.assertRaises(KeyError):
                s.erase(b)
            self.assertGreater(s.erase_all(), 0)
            self.assertEqual(s.records(), [])

    def test_wrong_turn_detector_prefers_precision(self):
        for said in ("That's wrong", "no, that is wrong", "Wrong.", "this is incorrect, try again",
                     "It doesn't work", "that's not what I asked", "nope, not right", "your program is wrong"):
            self.assertTrue(F.is_wrong_turn(said), said)
        for said in ("is it wrong to use a loop?", "what could go wrong here?", "write a program that finds "
                     "wrong answers", "thanks!", "Implement this specification in t.", ""):
            self.assertFalse(F.is_wrong_turn(said), said)

    def test_recorder_session_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = F.Recorder("tester", root=tmp, model={"base": "x"})
            self.assertIn("no answer", r.thumbs(True))
            conv = [{"role": "user", "content": USER},
                    {"role": "assistant", "content": [{"type": "t", "text": PROGRAM.replace("s + i_v", "s - i_v")},
                                                      {"type": "t_output", "text": "example 1: fail"}]}]
            rid = r.answered(conv)
            self.assertIsNone(r.user_turn("thanks, and now the next one"))
            said = r.user_turn("that's wrong, it should be:\n" + PROGRAM)
            self.assertIn("correction", said)
            row = r.store.get(rid)
            self.assertEqual(row["feedback"], "wrong")
            self.assertEqual(row["target"][0], {"type": "t", "text": PROGRAM})
            self.assertTrue(row["target"][1]["text"].endswith("example 2: pass"))    # the tool's real verdict
            self.assertIsNone(r.user_turn("that's wrong"))              # already rated: a later remark does not override
            rid2 = r.answered(conv)
            self.assertIn("Kept your version", r.edit_program(PROGRAM))
            self.assertEqual(r.store.get(rid2)["feedback"], "edit")
            examples, _ = r.store.training_examples()
            self.assertEqual({e["id"] for e in examples}, {rid, rid2})
            long = []
            for i in range(10):
                long += [{"role": "user", "content": f"turn {i}"}, {"role": "assistant", "content": f"reply {i}"}]
            kept = r.store.get(r.answered(long))["messages"]
            self.assertEqual(len(kept), r.KEEP_MESSAGES)
            self.assertEqual((kept[0]["role"], kept[-1]["content"]), ("user", "turn 9"))


# ---------------------------------------------------------------- persons --

class Persons(unittest.TestCase):
    def test_every_person_restyles_and_is_a_fixed_point(self):
        for name, person in P.PERSONS.items():
            for program, user in ((PROGRAM, USER), (BRANCHY, BRANCHY_USER), (SHADOWED, SHADOWED_USER)):
                answer = P.person_answer(person, program, user)
                self.assertIsNotNone(answer, (name, program[:30]))
                report = P.style_report(person, answer)
                self.assertEqual(report["adherence"], 1.0, (name, report))
                self.assertEqual(P.react(person, user, answer, program)["feedback"], "up", name)

    def test_rename_is_capture_free_and_case_insensitive(self):
        import surface
        task = P.rename_locals(surface.parse(SHADOWED), "upper")
        # the local i is bound again by no quantifier inside the body: renamed, but not to I (ensures binds i)
        self.assertEqual(P.locals_of(task), ["I2"])
        self.assertIn("forall i in", surface.print_task(task))              # the ensures binder is untouched
        text = P.restyle_program(PROGRAM, P.PERSONS["di"])
        self.assertIn("var I: int := 0;", text)
        self.assertIn("    var", text)                                        # four spaces
        k = P.restyle_program(PROGRAM, P.PERSONS["bo"])
        self.assertIn("var k1: int := 0\n", k)                                # no semicolons
        self.assertNotIn(";", k)

    def test_formatting_keeps_the_tree_and_if_form_round_trips(self):
        import surface
        cy = P.restyle_program(BRANCHY, P.PERSONS["cy"])
        self.assertIn("r := if x < 0 then -x else x;", cy)
        back = P.if_form(surface.parse(cy), expression=False)
        self.assertEqual(surface.canon(P.rename_locals(surface.parse(BRANCHY), "cur-snake")), surface.canon(back))
        t0 = BRANCHY.replace("t 1\n", "t 0\n", 1)
        self.assertNotIn("then", P.restyle_program(t0, P.PERSONS["cy"]))      # ite is v1: a t 0 task keeps its if

    def test_reaction_up_edit_wrong_and_cost(self):
        ada = P.PERSONS["ada"]
        styled = P.person_answer(ada, PROGRAM, USER)
        self.assertEqual(P.react(ada, USER, styled, PROGRAM)["cost"], 0)
        plain = P.react(ada, USER, PROGRAM, PROGRAM)
        self.assertEqual(plain["feedback"], "edit")
        self.assertGreater(plain["cost"], 0)
        broken = P.react(ada, USER, PROGRAM.replace("s + i_v", "s - i_v"), PROGRAM)
        self.assertEqual(broken["feedback"], "wrong")
        self.assertEqual(F.content_text(broken["target"]), F.content_text(styled))
        self.assertEqual(P.react(ada, USER, "", PROGRAM)["feedback"], "wrong")
        self.assertEqual(P.levenshtein([1, 2, 3], [1, 3]), 1)
        self.assertEqual(P.levenshtein([], [4, 5]), 2)
        self.assertEqual(P.levenshtein("kitten", "sitting"), 3)

    def test_explanation_counts_the_program(self):
        line = P.explanation(P.restyle_program(PROGRAM, P.PERSONS["ada"]))
        self.assertEqual(line, "Approach: 1 loop with 2 invariants; local myI; the result is s.")


# ------------------------------------------------------------- profile --

class Profile(unittest.TestCase):
    def examples(self, person, n=4):
        out = []
        for i in range(n):
            prog, user = PROGRAM.replace("count_up", f"count_up{i}"), USER.replace("count_up", f"count_up{i}")
            out.append({"messages": [{"role": "user", "content": user},
                                     {"role": "assistant", "content": P.person_answer(person, prog, user)}]})
        return out

    def test_infers_each_persons_mechanical_taste_and_applies_it(self):
        from dawnr_learning import profile as PR
        for name in ("ada", "bo", "cy", "di"):
            person = P.PERSONS[name]
            prof = {"inferred": PR.infer(self.examples(person)), "pinned": {}}
            prefs = PR.effective(prof)
            self.assertEqual(prefs["naming"], person.naming, name)
            self.assertEqual(prefs["semicolons"], person.semicolons, name)
            self.assertEqual(prefs["indent"], person.indent, name)
            self.assertEqual(prefs["tool"], person.tool, name)
            self.assertNotIn("if_expression", prefs)             # PROGRAM has no two-way assignment to vote with
            shown = PR.apply(prof, PROGRAM, USER)                    # the canonical answer, rewritten
            want = P.person_answer(person, PROGRAM, USER)
            if person.explain:                                       # free text is not a mechanical dimension
                want = [p for p in want if p["type"] != "text"]
            self.assertEqual(F.content_text(shown), F.content_text(want), name)
            self.assertEqual(P.style_report(person, shown)["features"]["naming"], 1.0)

    def test_undecided_until_enough_agreeing_votes_and_pins_win(self):
        from dawnr_learning import profile as PR
        two = PR.infer(self.examples(P.PERSONS["bo"], n=2))
        self.assertEqual(two, {})                                     # 2 votes < MIN_VOTES
        mixed = self.examples(P.PERSONS["bo"], 2) + self.examples(P.PERSONS["di"], 2)
        self.assertNotIn("naming", PR.infer(mixed))                   # 2 of 4 agree: not decided
        prof = {"inferred": PR.infer(self.examples(P.PERSONS["bo"])), "pinned": {"indent": 4}}
        self.assertEqual(PR.effective(prof)["indent"], 4)
        self.assertIn("indentation: 4 (set by you)", PR.describe(prof))
        self.assertEqual(PR.apply({"inferred": {}, "pinned": {}}, PROGRAM, USER), PROGRAM)
        self.assertEqual(PR.apply(prof, "no program here", USER), "no program here")

    def test_refresh_reads_the_store_and_keeps_pins(self):
        from dawnr_learning import profile as PR
        with tempfile.TemporaryDirectory() as tmp:
            s = F.PersonStore("cy", tmp)
            for ex in self.examples(P.PERSONS["cy"]):
                rid = s.add_answer(ex["messages"][:1], PROGRAM)
                s.edit(rid, ex["messages"][1]["content"])
            PR.save(s.dir, {"inferred": {}, "pinned": {"semicolons": False}})
            prof = PR.refresh(s)
            self.assertEqual(prof["inferred"]["naming"]["value"], "cur-snake")
            self.assertEqual(PR.effective(prof)["semicolons"], False)
            self.assertEqual(PR.load(s.dir)["examples"], 4)


# ------------------------------------------------------------- measure --

class Measure(unittest.TestCase):
    def convs(self):
        out = []
        for i in range(12):
            prog, user = PROGRAM.replace("count_up", f"count_up{i}"), USER.replace("count_up", f"count_up{i}")
            out.append({"source": f"count_up{i}", "split": "train" if i < 10 else "val",
                        "messages": [{"role": "user", "content": user}, {"role": "assistant", "content": prog}]})
        return out

    def test_problems_are_disjoint_and_fixed_by_the_registered_set(self):
        from dawnr_learning import measure as M
        people = [P.PERSONS["ada"], P.PERSONS["bo"]]
        chosen = M.choose(self.convs(), people, 2, 2, 2, guard_prompts=2)
        sessions = [c["source"] for s in chosen["sessions"] for c in s]
        held = [c["source"] for c in chosen["heldout_train"]]
        guard = [c["source"] for c in chosen["guard_prompts"]]
        replay = [c["source"] for c in chosen["replay_pool"]]
        self.assertEqual((len(sessions), len(held), len(guard), len(chosen["heldout_val"])), (4, 2, 2, 2))
        groups = [set(sessions), set(held), set(guard), set(replay)]
        self.assertEqual(sum(len(g) for g in groups), len(set().union(*groups)))     # pairwise disjoint
        self.assertEqual(len(replay), 2)
        self.assertEqual(M.choose(self.convs(), people, 2, 2, 2, guard_prompts=2)["sessions"], chosen["sessions"])
        with self.assertRaises(SystemExit):
            M.choose(self.convs(), people, 5, 2, 2)                                  # 12 are not enough

    def test_scores_zero_cost_for_the_persons_own_answers(self):
        from dawnr_learning import measure as M
        people = [P.PERSONS["ada"], P.PERSONS["di"]]
        problems = self.convs()[:3]
        own = [{"parts": P.person_answer(people[0], M.reference(c), M.user_of(c))} for c in problems]
        scored = M.score_answers(people, problems, own, None)
        self.assertEqual(scored["by_person"]["ada"]["cost_mean"], 0)
        self.assertEqual(scored["by_person"]["ada"]["adherence_mean"], 1.0)
        self.assertGreater(scored["by_person"]["di"]["cost_mean"], 0)
        self.assertEqual(scored["core"]["examples_pass"], 3)


# ------------------------------------------------------------- sleep data --

class SleepData(unittest.TestCase):
    def test_split_cap_and_gate(self):
        from dawnr_learning import sleep as S
        exs = [{"id": f"r{i}", "hash": f"h{i}", "messages": [{"role": "user", "content": f"task number {i}"},
                                                             {"role": "assistant", "content": PROGRAM}]}
               for i in range(10)]
        train, val = S.split_examples(exs, 0.2, 1)
        self.assertEqual((len(train), len(val)), (8, 2))
        self.assertEqual(S.split_examples(exs, 0.2, 1), (train, val))           # deterministic
        self.assertEqual(S.split_examples(exs[:1], 0.2, 1), (exs[:1], []))
        self.assertEqual(len(S.cap_examples(exs, 4, 0)), 4)
        self.assertEqual(S.cap_examples(exs, 4, 0), S.cap_examples(exs, 4, 0))
        if not SPLIT.is_file():
            self.skipTest("no split file")
        held = sorted(json.loads(SPLIT.read_text())["eval_ids"])[0]
        leak = {"id": "bad", "hash": "hb", "messages": [
            {"role": "user", "content": f"Implement mbpp_{held} please"}, {"role": "assistant", "content": PROGRAM}]}
        kept, refused = S.gate_examples(exs[:2] + [leak], SPLIT)
        self.assertEqual([e["id"] for e in kept], ["r0", "r1"])
        self.assertEqual([r["id"] for r in refused], ["bad"])


# ------------------------------------------------------------------ torch --

try:
    import torch
except ImportError:                                                     # pragma: no cover
    torch = None


def tiny(arch="gpt", vocab=None):
    import chat
    import data
    from model import GPT, GPTConfig
    tok = chat.with_chat_tokens(data.CharTokenizer.from_text(string.printable))
    torch.manual_seed(0)
    model = GPT(GPTConfig(vocab_size=tok.vocab_size, block_size=512, n_layer=2, n_head=2, n_embd=32,
                          architecture=arch))
    return model, tok


@unittest.skipIf(torch is None, "needs torch")
class LoRA(unittest.TestCase):
    def test_starts_at_the_base_switches_off_and_comes_off_exactly(self):
        from model import (add_lora, base_fingerprint, has_lora, lora_parameters, lora_state, load_lora_state,
                           merge_lora, remove_lora, set_lora_enabled)
        for arch in ("gpt", "modern"):
            model, _ = tiny(arch)
            model.eval()
            x = torch.randint(0, 50, (2, 12))
            ref = model(x)[0]
            fp = base_fingerprint(model)
            config = add_lora(model, r=4, alpha=8)
            self.assertEqual(config["targets"][2], "mlp.c_fc" if arch == "gpt" else "mlp.gate_up")
            self.assertTrue(torch.equal(model(x)[0], ref))
            self.assertTrue(all(p.requires_grad for p in lora_parameters(model)))
            self.assertEqual({n for n, p in model.named_parameters() if p.requires_grad},
                             {n for n, _ in model.named_parameters() if ".lora_" in n})
            with torch.no_grad():
                for p in lora_parameters(model):
                    p.add_(torch.randn_like(p) * 0.2)
            out = model(x)[0]
            self.assertFalse(torch.allclose(out, ref))
            set_lora_enabled(model, False)
            self.assertTrue(torch.equal(model(x)[0], ref))
            set_lora_enabled(model, True)
            state = lora_state(model)
            with self.assertRaises(ValueError):
                add_lora(model)
            remove_lora(model)
            self.assertFalse(has_lora(model))
            self.assertEqual(base_fingerprint(model), fp)
            self.assertTrue(all(p.requires_grad for p in model.parameters()))
            self.assertTrue(torch.equal(model(x)[0], ref))
            load_lora_state(model, state)
            self.assertTrue(torch.allclose(model(x)[0], out, atol=1e-6))
            merge_lora(model)
            self.assertFalse(has_lora(model))
            self.assertTrue(torch.allclose(model(x)[0], out, atol=1e-5))

    def test_refuses_an_adapter_for_another_model(self):
        from model import add_lora, lora_state, load_lora_state
        model, _ = tiny("gpt")
        add_lora(model, r=2)
        state = lora_state(model)
        other, _ = tiny("modern")
        with self.assertRaises(ValueError):
            load_lora_state(other, state)
        bigger, _ = tiny("gpt")
        add_lora(bigger, r=4)
        with self.assertRaises(ValueError):
            load_lora_state(bigger, state)

    def test_cached_generation_matches_uncached_with_an_adapter(self):
        from model import add_lora, lora_parameters
        model, _ = tiny("gpt")
        add_lora(model, r=4)
        with torch.no_grad():
            for p in lora_parameters(model):
                p.add_(torch.randn_like(p) * 0.2)
        idx = torch.randint(0, 50, (1, 5))
        a = model.generate(idx, 12, temperature=0.0, use_cache=True)
        b = model.generate(idx, 12, temperature=0.0, use_cache=False)
        self.assertTrue(torch.equal(a, b))


def person_rows(tok, n=6, person="bo"):
    from dawnr_learning import sleep as S
    p = P.PERSONS[person]
    convs = []
    for i in range(n):
        prog = PROGRAM.replace("count_up", f"count_up{i}")
        user = USER.replace("count_up", f"count_up{i}")
        convs.append({"id": str(i), "hash": str(i), "messages": [
            {"role": "user", "content": user}, {"role": "assistant", "content": P.person_answer(p, prog, user)}]})
    return S.Rows(tok, convs, 512), convs


@unittest.skipIf(torch is None, "needs torch")
class Sleep(unittest.TestCase):
    def test_trains_only_the_adapter_and_lowers_the_persons_loss(self):
        from dawnr_learning import sleep as S
        from model import base_fingerprint, has_lora
        model, tok = tiny()
        rows, _ = person_rows(tok)
        fp = base_fingerprint(model)
        cfg = S.SleepConfig(r=4, lr=1e-2, batch_size=4, replay_frac=0.25, min_steps=40, max_steps=40,
                            eval_every=10, patience=10, dropout=0.0, guard_tolerance=None)
        replay = S.Rows(tok, [{"messages": [{"role": "user", "content": "hi"},
                                            {"role": "assistant", "content": "hello"}]}], 512)
        state, record = S.train_adapter(model, tok, rows, rows, replay, cfg, "cpu")
        self.assertIsNotNone(state)
        self.assertTrue(has_lora(model))
        self.assertLess(record["loss_adapter"]["person_train"], record["loss_base"]["person_train"])
        self.assertEqual(record["rows"]["replay_rows_per_batch"], 1)
        self.assertEqual(record["base_fingerprint"], fp)
        self.assertEqual(record["best_step"], min((p for p in record["curve"]), key=lambda p: p["person_val"])["step"])

    def test_the_guard_refuses_an_adapter_that_hurts_plain_text(self):
        from dawnr_learning import sleep as S
        from model import has_lora
        model, tok = tiny()
        rows, _ = person_rows(tok)
        guard = S.GuardWindows(tok, string.printable * 40, 64, windows=4)
        cfg = S.SleepConfig(r=4, lr=5e-2, batch_size=4, replay_frac=0.0, min_steps=20, max_steps=20,
                            eval_every=10, dropout=0.0, guard_tolerance=-1.0)      # any rise at all is too much
        state, record = S.train_adapter(model, tok, rows, None, None, cfg, "cpu", guard=guard)
        self.assertIsNone(state)
        self.assertFalse(record["guard"]["ok"])
        self.assertFalse(has_lora(model))

    def test_the_behaviour_guard_keeps_the_last_state_that_still_passes(self):
        from dawnr_learning import sleep as S
        from model import has_lora

        class Scripted(S.BehaviorGuard):
            """Passes the base's 3 of 4, then the adapter's 3, then 1: the second check must end training."""
            def __init__(self):
                super().__init__(["unused"])
                self.results = [3, 3, 1, 1]

            def check(self, model, tokenizer):
                return {"passed": self.results.pop(0), "asked": 4, "each": []}

        model, tok = tiny()
        rows, _ = person_rows(tok)
        cfg = S.SleepConfig(r=4, lr=1e-2, batch_size=4, replay_frac=0.0, min_steps=40, max_steps=40,
                            eval_every=10, patience=10, dropout=0.0, guard_tolerance=None, behavior_tolerance=1)
        state, record = S.train_adapter(model, tok, rows, rows, None, cfg, "cpu", behavior=Scripted())
        self.assertIsNotNone(state)
        self.assertEqual(record["stop"], "behavior_guard")
        self.assertEqual(record["best_step"], 10)
        self.assertEqual(record["behavior"]["checks"], [{"step": 10, "passed": 3}, {"step": 20, "passed": 1}])
        self.assertTrue(has_lora(model))

        class Never(Scripted):
            def __init__(self):
                super().__init__()
                self.results = [4, 0]

        model, tok = tiny()
        state, record = S.train_adapter(model, tok, rows, rows, None, cfg, "cpu", behavior=Never())
        self.assertIsNone(state)
        self.assertFalse(record["behavior"]["ok"])
        self.assertFalse(has_lora(model))

    def test_the_behaviour_guard_asks_through_the_engine(self):
        from dawnr_learning import sleep as S
        model, tok = tiny()
        verdict = S.BehaviorGuard([USER], max_tokens=8).check(model, tok)
        self.assertEqual((verdict["asked"], verdict["passed"]), (1, 0))       # a random model writes no program

    def test_fisher_and_continue_with_ewc(self):
        from dawnr_learning import sleep as S
        from model import remove_lora
        model, tok = tiny()
        rows, _ = person_rows(tok, 4)
        cfg = S.SleepConfig(r=2, lr=1e-2, batch_size=2, replay_frac=0.0, min_steps=10, max_steps=10,
                            eval_every=5, dropout=0.0, guard_tolerance=None, fisher=True)
        state, _ = S.train_adapter(model, tok, rows, None, None, cfg, "cpu")
        fisher = state.pop("fisher")
        self.assertEqual(set(fisher), set(state["tensors"]))
        self.assertTrue(all((f >= 0).all() for f in fisher.values()))
        self.assertGreater(sum(float(f.sum()) for f in fisher.values()), 0)
        remove_lora(model)
        cont = S.SleepConfig(r=2, lr=1e-2, batch_size=2, replay_frac=0.0, min_steps=10, max_steps=10,
                             eval_every=5, dropout=0.0, guard_tolerance=None, mode="continue", ewc_lambda=10.0)
        new_rows, _ = person_rows(tok, 2, person="cy")
        state2, record = S.train_adapter(model, tok, new_rows, None, None, cont, "cpu", init_state=state,
                                         anchor={"theta": state["tensors"], "fisher": fisher}, old_rows=rows)
        self.assertIsNotNone(state2)
        self.assertEqual(record["rows"]["old_rows_per_batch"], 1)


@unittest.skipIf(torch is None, "needs torch")
class Adapters(unittest.TestCase):
    def test_save_attach_and_go_stale_when_an_example_is_erased(self):
        from dawnr_learning import adapters as A
        from dawnr_learning import sleep as S
        from model import has_lora, lora_state, remove_lora
        with tempfile.TemporaryDirectory() as tmp:
            model, tok = tiny()
            s = F.PersonStore("bo", root=tmp)
            _, convs = person_rows(tok, 3)
            ids = []
            for c in convs:
                rid = s.add_answer(c["messages"][:1], "wrong answer")
                s.edit(rid, c["messages"][1]["content"])
                ids.append(rid)
            examples, _ = s.training_examples()
            self.assertEqual(len(examples), 3)
            cfg = S.SleepConfig(r=2, lr=1e-2, batch_size=2, replay_frac=0.0, min_steps=4, max_steps=4,
                                eval_every=2, dropout=0.0, guard_tolerance=None)
            state, _ = S.train_adapter(model, tok, S.Rows(tok, examples, 512), None, None, cfg, "cpu")
            identity = {"ckpt_sha256": "ab" * 32, "tokenizer_fingerprint": "tok", "vocab_size": tok.vocab_size}
            directory = A.adapter_dir(s, identity)
            manifest = A.save_adapter(state, directory, {"base": identity, "examples": [
                {"id": e["id"], "hash": e["hash"]} for e in examples]})
            self.assertLess(manifest["bytes"], A.MAX_ADAPTER_BYTES)
            with self.assertRaises(ValueError):
                A.save_adapter(state, directory, {}, max_bytes=10)
            remove_lora(model)
            st = A.attach(model, s, identity)
            self.assertTrue(st["attached"] and has_lora(model))
            self.assertTrue(all(torch.equal(a, b) for a, b in zip(lora_state(model)["tensors"].values(),
                                                                  state["tensors"].values())))
            other = dict(identity, ckpt_sha256="cd" * 32)
            self.assertFalse(A.status(s, other)["exists"])            # another base: another folder
            s.erase(ids[1])
            st = A.status(s, identity)
            self.assertFalse(st["fresh"])
            self.assertIn("erased or corrected", st["why"])
            self.assertFalse(A.attach(model, s, identity)["attached"])
            self.assertFalse(has_lora(model))


@unittest.skipIf(torch is None, "needs torch")
class SleepPerson(unittest.TestCase):
    """The product path from files: a store, a checkpoint on disk, replay conversations, a held-out text."""

    def test_sleep_saves_a_fresh_adapter_then_forgetting_makes_it_stale(self):
        from dataclasses import asdict
        from data import tokenizer_fingerprint
        from dawnr_learning import adapters as A
        from dawnr_learning import sleep as S
        from dawnr_learning.__main__ import main as cli
        import io
        import contextlib
        with tempfile.TemporaryDirectory() as tmp:
            model, tok = tiny()
            d = Path(tmp) / "model"
            d.mkdir()
            torch.save({"model": model.state_dict(), "config": asdict(model.config),
                        "tokenizer_fingerprint": tokenizer_fingerprint(tok)}, d / "ckpt.pt")
            tok.save(d / "tokenizer.json")
            replay = Path(tmp) / "conv.jsonl"
            replay.write_text("\n".join(json.dumps({"split": "train", "messages": [
                {"role": "user", "content": f"say {w}"}, {"role": "assistant", "content": w}]})
                for w in ("one", "two", "three", "four")) + "\n")
            guard = Path(tmp) / "plain.txt"
            guard.write_text(string.printable * 60)
            people = Path(tmp) / "people"
            s = F.PersonStore("bo", people)
            _, convs = person_rows(tok, 4)
            ids = []
            for c in convs:
                rid = s.add_answer(c["messages"][:1], "not it")
                s.edit(rid, c["messages"][1]["content"])
                ids.append(rid)
            cfg = S.SleepConfig(r=2, lr=1e-2, batch_size=4, min_steps=6, max_steps=6, eval_every=3,
                                dropout=0.0, guard_tolerance=None)
            record = S.sleep_person(s, d, cfg=cfg, replay=replay, guard_text=guard, split=SPLIT, device="cpu",
                                    guard_chars=2000, behavior_prompts=2, log=None)
            self.assertEqual(record["result"], "saved", record.get("result"))
            self.assertEqual(record["rows"]["replay_pool"], 2)                 # two prompts went to the guard
            self.assertEqual(record["behavior"]["asked"], 2)
            identity = A.base_identity(d)
            self.assertTrue(A.status(s, identity)["fresh"])
            self.assertEqual(len(list((s.dir / "sleeps").glob("sleep-*.json"))), 1)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                cli(["--root", str(people), "show", "bo"])
                cli(["--root", str(people), "forget", "bo", ids[0]])
                cli(["--root", str(people), "status", "bo", "--model", str(d)])
            self.assertIn(ids[1], out.getvalue())
            self.assertFalse(A.status(s, identity)["fresh"])
            with self.assertRaises(ValueError):                                # continue would keep the erased one
                S.sleep_person(s, d, cfg=S.SleepConfig(mode="continue"), split=SPLIT, device="cpu", log=None)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli(["--root", str(people), "forget-all", "bo"]), 2)   # asks for --yes
                cli(["--root", str(people), "forget-all", "bo", "--yes"])
            self.assertFalse(s.dir.exists())


@unittest.skipIf(torch is None, "needs torch")
class Pane(unittest.TestCase):
    """What the chat window calls: off by default, nothing recorded until the base is identified."""

    def checkpoint(self, tmp):
        from dataclasses import asdict
        from data import tokenizer_fingerprint
        model, tok = tiny()
        d = Path(tmp) / "model"
        d.mkdir()
        torch.save({"model": model.state_dict(), "config": asdict(model.config),
                    "tokenizer_fingerprint": tokenizer_fingerprint(tok)}, d / "ckpt.pt")
        tok.save(d / "tokenizer.json")
        return d, model

    def test_off_until_turned_on_then_records_with_the_base(self):
        from dawnr_learning.pane import PaneLearning
        from model import has_lora
        with tempfile.TemporaryDirectory() as tmp:
            d, model = self.checkpoint(tmp)
            pane = PaneLearning(Path(tmp) / "people")
            self.assertFalse(pane.enabled())
            self.assertIsNone(pane.attach_adapter(model, d))
            conv = [{"role": "user", "content": USER}, {"role": "assistant", "content": PROGRAM}]
            pane.replied(conv)
            self.assertIn("Learning is off", pane.thumbs(True))
            self.assertFalse((Path(tmp) / "people" / "me").exists())            # nothing kept while off
            self.assertIn("on", pane.save_settings(True, "Ada"))
            self.assertEqual(pane.settings(), {"enabled": True, "person": "ada"})
            pane.replied(conv)                                                   # base not identified yet
            self.assertEqual(F.PersonStore("ada", Path(tmp) / "people").records(), [])
            said = pane.attach_adapter(model, d)
            self.assertIn("No adapter yet", said)
            self.assertFalse(has_lora(model))
            pane.replied(conv)
            self.assertIn("Kept", pane.thumbs(True))
            self.assertEqual(pane.last_answer_text(), PROGRAM)
            rows = F.PersonStore("ada", Path(tmp) / "people").records()
            self.assertEqual([r["feedback"] for r in rows], ["up"])
            self.assertEqual(len(rows[0]["model"]["ckpt_sha256"]), 64)             # kept with the weights that wrote it
            self.assertIn("off", pane.save_settings(False, "ada"))
            self.assertIsNone(pane.user_turn("that's wrong"))
            with self.assertRaises(ValueError):
                pane.save_settings(True, "../elsewhere")


if __name__ == "__main__":
    unittest.main()
