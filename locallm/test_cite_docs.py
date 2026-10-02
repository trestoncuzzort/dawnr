"""cite_docs.py: passages, BM25 picking, and how a cited reply or a refusal is shown (no model server)."""
from locallm import cite_docs as cd, rag_cite as rc

NOTES = """The lab moved to building C in March. Its door code is 4417.

The new GPU arrives on Friday. It is an RTX 6000.
- Ask Dana before booking the cluster."""


def test_sentences_and_passages(tmp_path):
    f = tmp_path / "notes.txt"; f.write_text(NOTES)
    assert cd.sentences(NOTES)[:2] == ["The lab moved to building C in March.", "Its door code is 4417."]
    assert "- Ask Dana before booking the cluster." in cd.sentences(NOTES)
    ps = cd.passages([f], size=2)
    assert [p["title"] for p in ps] == ["notes.txt, part 1", "notes.txt, part 2", "notes.txt, part 3"]


def test_pick_ranks_by_shared_words_and_finds_nothing_for_an_unrelated_question(tmp_path):
    f = tmp_path / "notes.txt"; f.write_text(NOTES)
    ps = cd.passages([f], size=2)
    assert cd.pick(ps, "what is the door code?", k=1)[0]["title"] == "notes.txt, part 1"
    assert cd.pick(ps, "zebra quantum", k=3) == []


def test_render_shows_each_claim_with_its_quote_and_source_or_says_it_is_not_there(tmp_path):
    docs = [{"title": "notes.txt, part 1", "sentences": ["Its door code is 4417."]}]
    out = cd.render("%<4417>%(Document 1)%[Its door code is 4417.]%", docs)
    assert out.splitlines() == ["4417", '    "Its door code is 4417."', "    (notes.txt, part 1)"]
    assert cd.render(rc.REJECT, docs).startswith("NOT IN YOUR FILES")


def test_ask_sends_the_grammar_that_binds_quotes_to_the_picked_passages():
    docs = [{"title": "a", "sentences": ["Its door code is 4417."]}]
    seen = {}

    def post(url, body):
        seen.update(body); return {"choices": [{"message": {"content": rc.REJECT}}]}
    assert cd.ask("h:1", "door code?", docs, post=post) == rc.REJECT
    assert '"Its door code is 4417."' in seen["grammar"] and seen["temperature"] == 0
