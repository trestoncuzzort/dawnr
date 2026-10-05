"""extract_docs.py: a field's value is a run of words of one of the person's sentences or the field stays empty;
the grammar that holds the reply to that, the typed readings, and how a row is shown (no model server)."""
import itertools
import json
import re

import pytest

from locallm import extract_docs as ex

NOTE = """Invoice 2291 from Harbor Supply. The total due is $1,250.00, payable by March 3, 2026.

Ship to the dock office. Questions go to accounts@harbor.example."""


def reply_ok(grammar: str, reply: str) -> bool:
    """A small reading of the grammar this module writes: does `reply` match root? (llama.cpp's own parser is the
    real one; this keeps the tests off a server.)"""
    rules = dict(line.split(" ::= ", 1) for line in grammar.strip().splitlines())

    def match(expr: str, text: str) -> set[int]:
        """Every length of a prefix of `text` that `expr` (a sequence with optional groups) can produce."""
        tokens = re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)\?|\)|\||[a-z0-9]+', expr)

        def seq(i: int, ends: set[int]) -> tuple[int, set[int]]:
            alts, cur = set(), set(ends)
            while i < len(tokens) and tokens[i] not in (")", ")?"):
                tok = tokens[i]
                if tok == "|":
                    alts |= cur
                    cur = set(ends)
                    i += 1
                elif tok == "(":
                    j, inner = seq(i + 1, cur)
                    cur = inner | (cur if tokens[j] == ")?" else set())
                    i = j + 1
                elif tok.startswith('"'):
                    lit = json.loads(tok)
                    cur = {e + len(lit) for e in cur if text.startswith(lit, e)}
                    i += 1
                else:
                    cur = set(itertools.chain.from_iterable(({e + n for n in match(rules[tok], text[e:])} for e in cur)))
                    i += 1
            return i, alts | cur
        return seq(0, {0})[1]
    return len(reply) in match(rules["root"], reply)


def test_a_field_is_read_with_its_kind_and_what_it_is():
    assert ex.read_field("total(number): the amount due") == {"name": "total", "kind": "number", "description": "the amount due"}
    assert ex.read_field("vendor: who sent it") == {"name": "vendor", "kind": "text", "description": "who sent it"}
    assert ex.read_field("due date(date)") == {"name": "due date", "kind": "date", "description": "due date"}
    with pytest.raises(ValueError, match="a field is written"):
        ex.read_field("(number): nameless")


def test_any_run_of_pieces_is_a_substring_of_the_sentence_as_it_is_spaced():
    s = "The total due is $1,250.00, payable by March 3, 2026."
    ps = ex.pieces(s)
    assert [p for p, _ in ps][4:8] == ["$", "1,250.00", ",", "payable"]
    for i in range(len(ps)):
        for j in range(i + 1, len(ps) + 1):
            run = "".join((" " if spaced and k > i else "") + text for k, (text, spaced) in enumerate(ps[i:j], i))
            assert run in s, run


def test_the_grammar_admits_none_and_runs_of_a_sentences_own_words_and_nothing_else():
    sentences = ["The total due is $1,250.00, payable by March 3, 2026.", "Ship to the dock office."]
    g = ex.grammar(sentences)
    for good in ("NONE", "S1: 1,250.00", "S1: $1,250.00", "S1: March 3, 2026", "S2: dock office", "S2: Ship to the dock office."):
        assert reply_ok(g, good), good
    for bad in ("S1: 1250", "S1: total payable", "S2: 1,250.00", "S3: Ship", "S1: ", "none", "S1: 1,250.00 and more"):
        assert not reply_ok(g, bad), bad


def test_a_typed_field_is_offered_only_the_runs_that_read_as_its_kind():
    sentences = ["Invoice date: 12 February 2026.", "The total due is $1,250.00, payable by March 3, 2026.", "Ship to the dock office."]
    assert ex.typed_spans("date", sentences[0]) == ["12 February 2026"]
    assert ex.typed_spans("date", sentences[1]) == ["March 3, 2026"]
    assert ex.typed_spans("number", sentences[1]) == ["1,250.00", "3", "2026"] and ex.typed_spans("number", sentences[2]) == []
    dates = ex.grammar(sentences, "date")
    assert reply_ok(dates, "S2: March 3, 2026") and reply_ok(dates, "S1: 12 February 2026") and reply_ok(dates, "NONE")
    for bad in ("S2: 3, 2026", "S2: 1,250.00", "S3: Ship", "S1: February 2026"):
        assert not reply_ok(dates, bad), bad
    numbers = ex.grammar(sentences, "number")
    assert reply_ok(numbers, "S2: 1,250.00") and not reply_ok(numbers, "S2: $1,250.00") and "s3" not in numbers
    # nothing of the kind anywhere: the field is empty and no model is asked
    asked = []
    assert ex.ask("h:1", ex.read_field("weight(number): shipping weight"), ["Ship to the dock office."],
                  lambda url, body: asked.append(body)) == "NONE" and not asked


def test_a_reply_is_taken_only_when_its_words_are_in_the_sentence_it_names():
    sentences = ["The total due is $1,250.00.", "Ship to the dock office."]
    assert ex.parse("S1: 1,250.00", sentences) == (1, "1,250.00")
    assert ex.parse("NONE", sentences) is None and ex.parse("S2: 1,250.00", sentences) is None
    assert ex.parse("S9: Ship", sentences) is None and ex.parse("the total is 1,250.00", sentences) is None


@pytest.mark.parametrize("kind, words, value, why", [
    ("number", "$1,250.00", 1250.0, None), ("number", "12 crates", 12, None), ("number", "-3", -3, None),
    ("number", "twelve", None, "the words picked hold no number"),
    ("date", "March 3, 2026", "2026-03-03", None), ("date", "3 March 2026", "2026-03-03", None),
    ("date", "2026-03-03", "2026-03-03", None), ("date", "March 3rd, 2026", "2026-03-03", None),
    ("date", "25/12/2026", "2026-12-25", None), ("date", "12/25/2026", "2026-12-25", None),
    ("date", "03/04/2026", None, "the date can be read day first or month first"),
    ("date", "next Tuesday", None, "the words picked do not read as a date"),
    ("text", "Harbor Supply", "Harbor Supply", None),
])
def test_a_typed_field_reads_as_its_kind_or_says_why_not(kind, words, value, why):
    assert ex.typed(kind, words) == (value, why)


def served(replies: dict):
    """A stand-in for the server: answers by the field named in the prompt, and records what it was sent."""
    seen = []

    def post(url, body):
        seen.append(body)
        field = body["messages"][-1]["content"].rsplit("Field: ", 1)[1].split(":")[0]
        return {"choices": [{"message": {"content": replies[field]}}]}
    post.seen = seen
    return post


def test_each_field_comes_back_with_its_sentence_and_file_or_is_left_empty(tmp_path):
    f = tmp_path / "invoice.txt"
    f.write_text(NOTE)
    sentences = ex.located([f])
    fields = [ex.read_field(x) for x in ("total(number): the amount due", "due(date): when payment is due",
                                         "vendor: who sent the invoice", "po: the purchase order number", "weight(number): shipping weight")]
    post = served({"total": "S2: 1,250.00", "due": "S2: March 3, 2026", "vendor": "S1: Harbor Supply", "po": "NONE",
                   "weight": "S3: dock office"})
    rows = {r["name"]: r for r in ex.extract("h:1", fields, sentences, post)}
    assert rows["total"]["value"] == 1250.0 and rows["total"]["words"] == "1,250.00" and rows["total"]["n"] == 2
    assert rows["due"]["value"] == "2026-03-03" and rows["vendor"]["value"] == "Harbor Supply" and rows["vendor"]["file"] == "invoice.txt"
    assert rows["po"] == {"name": "po", "kind": "text", "value": None, "why": "no sentence shown states it"}
    assert rows["weight"]["value"] is None and rows["weight"]["why"] == "the words picked hold no number"
    # the document is sent the same way for every field, so the server reads it once
    heads = {body["messages"][-1]["content"].rsplit("\n\nField: ", 1)[0] for body in post.seen}
    assert len(heads) == 1 and all(body["grammar"].startswith('root ::= "NONE" | s') for body in post.seen)
    text = ex.render(list(rows.values()))
    assert 'total   1250.0\n            "The total due is $1,250.00, payable by March 3, 2026." (invoice.txt, sentence 2)' in text
    assert "po      NOT STATED: no sentence shown states it." in text
    assert 'weight  NOT TAKEN: the words picked hold no number ("dock office")' in text


def test_a_reply_outside_the_grammar_is_never_shown(tmp_path):
    f = tmp_path / "invoice.txt"
    f.write_text(NOTE)
    rows = ex.extract("h:1", [ex.read_field("total(number): the amount due")], ex.located([f]),
                      served({"total": "S2: 9,999.00"}))
    assert rows[0]["value"] is None and rows[0]["why"] == "no sentence shown states it"


def test_a_long_document_is_cut_to_the_passages_that_match_the_field(tmp_path):
    f = tmp_path / "long.txt"
    f.write_text(" ".join(f"Filler sentence number {i} about nothing." for i in range(60))
                 + " The warranty lasts 24 months. " + " ".join(f"More filler {i} here." for i in range(60)))
    sentences = ex.located([f])
    shown = ex.candidates(sentences, ex.read_field("warranty: how long the warranty lasts"))
    assert len(sentences) > ex.WHOLE and len(shown) <= 30 and any("warranty lasts 24 months" in s["text"] for s in shown)
    assert ex.candidates(sentences[:10], ex.read_field("warranty")) == sentences[:10]


def test_the_command_refuses_a_missing_file_and_a_field_it_cannot_read(tmp_path, capsys):
    assert ex.main(["--host", "h:1", "--field", "a: b", str(tmp_path / "absent.txt")]) == 2
    f = tmp_path / "x.txt"
    f.write_text("One sentence.")
    assert ex.main(["--host", "h:1", "--field", "(number): nameless", str(f)]) == 2
    assert "a field is written" in capsys.readouterr().err
