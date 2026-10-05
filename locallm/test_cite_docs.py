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


def test_an_abbreviation_inside_a_sentence_does_not_end_it():
    text = "Goods remain the property of Harbor Supply Co. until paid in full. Returns are accepted within 30 days. see the terms."
    assert cd.sentences(text) == ["Goods remain the property of Harbor Supply Co. until paid in full.",
                                  "Returns are accepted within 30 days. see the terms."]
    assert cd.sentences('He said "No." Then he left. (It was late.) 3 people stayed.') == ['He said "No."', "Then he left.", "(It was late.)", "3 people stayed."]


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


ZH = "发票编号为2291。应付总额为1250美元，须于2026年3月3日前支付。如有疑问，请联系accounts@harbor.example。货物将运至码头办公室。"


def test_sentences_end_where_each_script_ends_them():
    """A profile of Unicode's rules (UAX #29): the ASCII rule read by category beyond ASCII, and the other scripts'
    own terminals, which need no space after them."""
    assert cd.sentences(ZH) == ["发票编号为2291。", "应付总额为1250美元，须于2026年3月3日前支付。", "如有疑问，请联系accounts@harbor.example。", "货物将运至码头办公室。"]
    assert cd.sentences("請求書番号は2291です。「ご質問は」こちらまで。次の文です！") == ["請求書番号は2291です。", "「ご質問は」こちらまで。", "次の文です！"]
    assert cd.sentences("चालान संख्या 2291 है। कुल देय राशि 1,250 डॉलर है। प्रश्न?") == ["चालान संख्या 2291 है।", "कुल देय राशि 1,250 डॉलर है।", "प्रश्न?"]
    assert cd.sentences("رقم الفاتورة 2291. هل لديكم أسئلة؟ راسلونا.") == ["رقم الفاتورة 2291.", "هل لديكم أسئلة؟", "راسلونا."]
    assert cd.sentences("Facture 2291. Échéance le 3 mars. À régler par virement.") == ["Facture 2291.", "Échéance le 3 mars.", "À régler par virement."]
    assert cd.sentences("Счёт № 2291. Общая сумма 1250 долларов. Вопросы пишите нам.") == ["Счёт № 2291.", "Общая сумма 1250 долларов.", "Вопросы пишите нам."]
    assert cd.sentences("«Hola.» ¿Preguntas? Escriba.") == ["«Hola.»", "¿Preguntas?", "Escriba."]
    # a closing mark stays with its sentence, and a run of terminals is not cut in the middle
    assert cd.sentences("他说：「好。」然后走了！！真的。") == ["他说：「好。」", "然后走了！！", "真的。"]


def test_english_is_split_exactly_as_every_measurement_split_it():
    """The rule cite and extract were measured with, kept here as it was written, beside the profile that replaced it."""
    import re
    measured = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][\"'”’)\]]))\s+(?=[A-Z0-9\"'“‘(\[])|\n\s*\n|\n(?=\s*[-*•]\s)")

    def as_measured(text):
        return [s for s in (" ".join(part.split()) for part in measured.split(text)) if len(s) >= 3]
    texts = ['Invoice 2291 from Harbor Supply Co. until paid. The total is $1,250.00, payable by March 3, 2026.\n\n'
             'Ship to the dock office. "Really?" he asked. It is e.g. fine. See p. 4 (the annex).\n- item one\n- item two',
             "He said \"Stop.\" Then left! (Really.) [Yes.] 'No.' It was 3 p.m. on Jan. 5. The U.S. agreed... Fine?\n\n\nNew part.\n * a point\n• another",
             "No capital follows. so it goes on. 10 items; see e.g. the list.\nA new line is not a break. End"]
    for text in texts:
        assert cd.sentences(text) == as_measured(text), text
    assert cd.sentences(texts[0])[:2] == ["Invoice 2291 from Harbor Supply Co. until paid.", "The total is $1,250.00, payable by March 3, 2026."]
    assert "See p." in cd.sentences(texts[0])                   # a known limit of the rule: an abbreviation before a number


def test_no_text_is_dropped_from_a_sentence_too_long_for_the_grammar():
    long = "The supplier shall deliver " + ", ".join(f"item {i} of the annex" for i in range(60)) + " without delay."
    parts = cd.sentences(long)
    assert len(long) > 2 * cd.LONGEST and len(parts) >= 3 and all(len(p) <= cd.LONGEST for p in parts)
    assert " ".join(parts) == long and all(p.endswith(",") for p in parts[:-1])        # cut after a clause mark, nothing lost
    unbroken = "x" * 1000
    assert cd.sentences(unbroken) == ["x" * 400, "x" * 400, "x" * 200]
    thai = "ใบแจ้งหนี้เลขที่ 2291 " * 40
    assert "".join(cd.sentences(thai)).replace(" ", "") == thai.replace(" ", "")


def test_the_passages_that_match_a_question_are_found_in_any_script(tmp_path):
    f = tmp_path / "invoice.txt"
    f.write_text("\n\n".join(["发票编号为2291。货物将运至码头办公室。"] * 3 + ["应付总额为1250美元，须于2026年3月3日前支付。"] + ["如有疑问，请联系我们。"] * 3), encoding="utf-8")
    ps = cd.passages([f], size=1)
    assert [p["sentences"] for p in cd.pick(ps, "应付总额是多少？", 1)] == [["应付总额为1250美元，须于2026年3月3日前支付。"]]
    g = tmp_path / "rechnung.txt"
    g.write_text("Die Lieferung erfolgt an das Hafenbüro.\n\nDer Gesamtbetrag beträgt 1.250,00 €.\n\nFragen an uns.", encoding="utf-8")
    assert cd.pick(cd.passages([g], size=1), "Wie hoch ist der Gesamtbetrag?", 1)[0]["sentences"] == ["Der Gesamtbetrag beträgt 1.250,00 €."]
