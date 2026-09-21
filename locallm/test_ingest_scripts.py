"""Real text, real scripts, real encodings: what read_any does with files a
person actually has.

WHY A SECOND INGEST TEST FILE. test_ingest.py pins the extension rule and
test_ingest_any.py pins the contract and the refusals. Neither one builds a
corpus in a writing system that is not Latin, and neither one checks the single
claim this round was worth making: THE SAME WORDS, SAVED THREE WAYS, MUST COME
BACK AS ONE STRING. Everything here is built with Python's own encoders and read
off a real temporary directory, because the defect being guarded against was a
decode that produced a plausible-looking string, and only a byte-for-byte
comparison against the original catches that.

THE RED WITNESS, measured on this machine 2026-09-21 with the line read_any
replaced — `read_text(encoding="utf-8", errors="ignore")` — over the same 2,520
character English text used below:

    saved as UTF-8            2,520 characters   (unaffected, as it must be)
    saved as UTF-8 with BOM   2,521 characters, and the first one is U+FEFF:
                              the mark itself became a character in the corpus,
                              so the alphabet gained a row nobody typed
    saved as UTF-16 LE+BOM    5,040 characters, 2,520 of them NUL — it does not
                              truncate, it INFLATES, and NUL becomes a
                              permanent embedding row
    letter in cp1252          1,143 of 1,269 characters: all 126 accented ones
                              deleted in silence, "Café au lait" arriving as
                              "Caf au lait"

Each of those four numbers is asserted against below, so the tests fail if the
old behaviour ever comes back.

NEITHER TORCH NOR A DISPLAY. ingest.py needs neither, and the one home.py
function exercised here is the off-thread reader, called as an unbound method
against a stand-in the way test_home.py already does it.
"""
from __future__ import annotations

import codecs
import pathlib
import queue
import tempfile
import unittest
import zipfile

import home
import ingest
import look

# --------------------------------------------------------------------------
# THE CORPORA. Prose first, then, for Chinese, a sweep of the Han block.
#
# WHY THE SWEEP IS NOT CHEATING and why the prose alone is not enough: the
# thing being tested is what happens to a corpus whose ALPHABET is thousands of
# characters, which is the ordinary case for Chinese and the case make_corpus's
# VOCAB_WARN and home.say_vocab exist for. Five paragraphs of Chinese carry
# about 150 distinct characters; a book carries thousands. The block range is
# unicode.org/Public/UCD/latest/ucd/Blocks.txt, CJK Unified Ideographs
# U+4E00-U+9FFF, and the characters are laid out as seven-character lines with
# the ideographic comma and full stop so the text has line structure to lose.
# --------------------------------------------------------------------------
ARABIC_PARAS = (
    "اللغة العربية هي إحدى أكثر اللغات انتشارا في العالم، ويتحدث بها مئات "
    "الملايين من الناس في الوطن العربي وخارجه. تكتب من اليمين إلى اليسار، "
    "وحروفها ثمانية وعشرون حرفا، تتصل ببعضها في الكلمة الواحدة.",
    "يقول الكاتب إن القراءة بابٌ لا يُغلق، وإن من قرأ كتابا واحدا بعناية "
    "خير ممن قلّب مئة كتاب على عجل. والكتب، كما قيل، خير جليس في الزمان.",
    "في الصباح الباكر خرج الفتى من البيت، وحمل معه رغيفا وكتابا، ومشى في "
    "الطريق الترابي حتى بلغ النهر. جلس على حجر كبير وفتح الكتاب، وقرأ حتى "
    "مالت الشمس إلى الغروب.",
    "العلم نورٌ، والجهل ظلامٌ، ومن سار على الدرب وصل. هكذا كانت جدتي تقول "
    "لنا ونحن صغار، وكنا نضحك، ثم كبرنا وفهمنا أنها كانت تقول شيئا صحيحا.",
)
CHINESE_PARAS = (
    "天行健，君子以自强不息；地势坤，君子以厚德载物。",
    "学而时习之，不亦说乎？有朋自远方来，不亦乐乎？人不知而不愠，不亦君子乎？",
    "春天来了，山上的雪化成水，顺着石头流进村口的小河里。孩子们放学以后，"
    "常常跑到河边去捉小鱼，一直玩到太阳落山才回家吃饭。",
    "读书的时候不要着急，一句一句地读，读不懂就放在那里，过些日子再回头看，"
    "往往就明白了。这是我父亲教给我的办法。",
)
ENGLISH = (
    "The Notepad problem.\n"
    "\n"
    "A person writes two thousand words in Notepad, reaches the Save as box, "
    "and picks the line below the one they meant. The file is now UTF-16, "
    "which is an ordinary thing for a Windows text file to be, and every "
    "second byte in it is a zero.\n"
    "\n"
    "Read as UTF-8 with errors set to ignore, that file comes back as almost "
    "nothing at all, and nothing anywhere says so. The count on the screen is "
    "smaller than it should be, but nobody knows what it should be, so the "
    "number is believed. Training starts. A model is produced. It is the "
    "wrong model, and it was produced without one word of warning.\n"
    "\n"
    "The rule that fixes it is not clever. Decode the file properly and say "
    "which encoding worked, or refuse it and say why in a sentence somebody "
    "can act on. There is no third answer, and a partly decoded string is not "
    "an answer at all.\n"
) * 3
#: Every accented letter, curly quote and dash below is in cp1252 and NOT in
#: ASCII, which is what makes the count meaningful: under errors="ignore" all of
#: them vanish and the sentence still reads like a sentence.
CP1252_LETTER = (
    "Café au lait, s'il vous plaît.\n"
    "Grüße aus München — die Prüfung war schwierig, aber Sören hat sie "
    "bestanden.\n"
    "Señor Núñez viajó a Málaga en agosto; la señora Peña se quedó en casa.\n"
    "Le garçon a déjà mangé; l'hôtel est près de la gare, à côté du théâtre.\n"
    "Naïve, résumé, façade, piñata, jalapeño, Zürich, Åre, Ørsted.\n"
    "“Curly quotes” and ‘single’ ones, an em dash — and an ellipsis… all of "
    "which cp1252 has and Latin-1 does not.\n"
) * 3


def arabic_corpus() -> str:
    text = "\n\n".join(ARABIC_PARAS)
    while len(text) < 4000:
        text += "\n\n" + ARABIC_PARAS[len(text) % len(ARABIC_PARAS)]
    return text


def chinese_corpus(sweep: int = 2600) -> str:
    lines = []
    pool = [chr(cp) for cp in range(0x4E00, 0x4E00 + sweep)]
    for i in range(0, len(pool), 7):
        lines.append("".join(pool[i:i + 7]) + ("。" if i % 21 == 0 else "，"))
    body = "\n".join(CHINESE_PARAS)
    return body + "\n\n" + "\n".join(lines) + "\n" + body + "\n"


def word_docx(path: pathlib.Path) -> str:
    """A .docx assembled with zipfile, and the text it must give back.

    The part names and the relationship type are the ones _docx_main_part looks
    for: "_rels/.rels" carrying the officeDocument relationship, which is how
    python-docx finds the document part (src/docx/opc/constants.py, RT.
    OFFICE_DOCUMENT). w:tab and w:noBreakHyphen are here because they are two of
    the six elements python-docx's CT_R.text joins, and a reader that takes only
    w:t loses both of them silently.
    """
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    paras = (
        '<w:p><w:r><w:t xml:space="preserve">A Word document nobody has to '
        'install anything to read.</w:t></w:r></w:p>',
        '<w:p><w:r><w:t xml:space="preserve">Second paragraph, with a</w:t>'
        '<w:tab/><w:t xml:space="preserve">tab in it.</w:t></w:r></w:p>',
        '<w:p><w:r><w:t xml:space="preserve">Third: Grüße, café, '
        'and a non</w:t><w:noBreakHyphen/>'
        '<w:t xml:space="preserve">breaking hyphen.</w:t></w:r></w:p>',
    )
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships"><Relationship Id="rId1" Type="http://schemas.'
            'openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" Target="word/document.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml",
                   f'<w:document xmlns:w="{w}"><w:body>' + "".join(paras) +
                   "</w:body></w:document>")
    return ("A Word document nobody has to install anything to read.\n"
            "Second paragraph, with a\ttab in it.\n"
            "Third: Grüße, café, and a non‑breaking hyphen.")


def epub_book(path: pathlib.Path) -> None:
    """An .epub assembled with zipfile, with one chapter the spine leaves out.

    The container path, the namespaces and the spine/manifest wiring are from
    the EPUB 3.3 Recommendation (w3.org/TR/epub-33): META-INF/container.xml,
    rootfile's full-path, and itemref idref naming a manifest item. The unused
    chapter is the point of the fixture — a real book carries leftovers, and
    reading the zip listing instead of the spine picks them up.
    """
    page = ("<?xml version='1.0' encoding='utf-8'?>"
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{t}</title>'
            "<style>p {{ color: red }}</style></head><body><h1>{t}</h1>"
            "<p>{body}</p>"
            "<script>var never = 'SCRIPT TEXT';</script></body></html>")
    opf = ('<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
           '<manifest>'
           '<item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
           '<item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/>'
           '<item id="old" href="old.xhtml" media-type="application/xhtml+xml"/>'
           '</manifest>'
           '<spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>')
    container = ('<container version="1.0" xmlns="urn:oasis:names:tc:'
                 'opendocument:xmlns:container"><rootfiles><rootfile '
                 'full-path="OEBPS/content.opf" media-type="application/'
                 'oebps-package+xml"/></rootfiles></container>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/ch1.xhtml",
                   page.format(t="Chapter One", body="It opens on a cold "
                                                     "morning."))
        z.writestr("OEBPS/ch2.xhtml",
                   page.format(t="Chapter Two", body="Und hier steht ein Satz "
                                                     "mit Grüßen."))
        z.writestr("OEBPS/old.xhtml",
                   page.format(t="Old", body="LEFTOVER FROM AN EARLIER EDITION"))


#: A real PDF header and enough of a body to look like one. rfc-editor.org/rfc/
#: rfc8118.txt section 8: "All PDF files start with the characters \"%PDF-\"".
PDF_BYTES = (b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
             b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 720 Td "
             b"(Hello) Tj ET\nendstream\nendobj\ntrailer\n<< /Root 1 0 R >>\n"
             b"%%EOF\n")


class Fixtures:
    """One temporary directory of real files per test that needs it.

    A MIXIN AND NOT A TestCase SUBCLASS: unittest collects any TestCase it can
    see, so a shared base with no test methods in it is reported as an error
    ("runTest / No test") on every run.
    """

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def write(self, name: str, data: bytes) -> pathlib.Path:
        p = self.tmp / name
        p.write_bytes(data)
        return p


class OneTextSavedThreeWays(Fixtures, unittest.TestCase):
    """The headline: UTF-8, UTF-8 with a BOM and UTF-16 are one string.

    A Windows Save as box offers ANSI, UTF-8, UTF-8 with BOM, UTF-16 LE and
    UTF-16 BE (learn.microsoft.com/en-us/answers/questions/2152989/windows-10-
    notepad-encoding-options), so three of these five are one keystroke apart
    from each other. Whichever one somebody picked, the corpus must be the same.
    """

    def setUp(self):
        super().setUp()
        self.plain = self.write("plain.txt", ENGLISH.encode("utf-8"))
        self.bom = self.write("bom.txt", codecs.BOM_UTF8 + ENGLISH.encode("utf-8"))
        # str.encode("utf-16") writes the mark and then little endian, which is
        # what Notepad's "UTF-16 LE" produces.
        self.wide = self.write("wide.txt", ENGLISH.encode("utf-16"))

    def test_all_three_give_back_the_same_string(self):
        got = [ingest.read_any(p) for p in (self.plain, self.bom, self.wide)]
        for r, p in zip(got, (self.plain, self.bom, self.wide)):
            self.assertIsNotNone(r.text, f"{p.name} was refused")
            self.assertEqual(r.dropped, 0, f"{p.name} dropped characters")
        self.assertEqual(got[0].text, ENGLISH,
                         "the UTF-8 file did not come back as what was written")
        self.assertEqual(got[0].text, got[1].text,
                         "a byte order mark changed the text")
        self.assertEqual(got[1].text, got[2].text,
                         "UTF-16 did not come back as the same text")
        self.assertEqual({len(r.text) for r in got}, {len(ENGLISH)})

    def test_the_mark_itself_never_becomes_a_character(self):
        """U+FEFF in the corpus is a row of the embedding table nobody typed."""
        for p in (self.plain, self.bom, self.wide):
            self.assertNotIn("﻿", ingest.read_any(p).text,
                             f"{p.name} kept its byte order mark as text")

    def test_each_one_says_which_encoding_worked(self):
        self.assertEqual(ingest.read_any(self.plain).encoding, "utf-8")
        self.assertIn("BOM", ingest.read_any(self.bom).encoding)
        self.assertIn("utf-16", ingest.read_any(self.wide).encoding)

    def test_the_red_witness_the_old_line_would_have_produced(self):
        """Measured, not asserted from memory: what errors="ignore" does here."""
        loose = self.wide.read_text(encoding="utf-8", errors="ignore")
        self.assertEqual(len(loose), 2 * len(ENGLISH),
                         "UTF-16 read as UTF-8 inflates rather than truncates")
        self.assertEqual(loose.count("\x00"), len(ENGLISH),
                         "every NUL would have become an embedding row")
        marked = self.bom.read_text(encoding="utf-8", errors="ignore")
        self.assertEqual(marked[0], "﻿",
                         "the mark would have become the first character")
        self.assertEqual(len(marked), len(ENGLISH) + 1,
                         "one character longer than the text, and that one is "
                         "an extra row of the embedding table")


class AnAlphabetThatIsNotLatin(Fixtures, unittest.TestCase):
    """Arabic and Chinese, read whole, with the counts a person can check."""

    def test_arabic_comes_back_character_for_character(self):
        text = arabic_corpus()
        p = self.write("arabic.txt", text.encode("utf-8"))
        got = ingest.read_any(p)
        self.assertEqual(got.text, text)
        self.assertEqual(got.encoding, "utf-8")
        self.assertEqual(got.dropped, 0)
        self.assertGreater(len(got.text), 3000, "a few thousand characters")

    def test_chinese_keeps_an_alphabet_of_thousands(self):
        text = chinese_corpus()
        p = self.write("chinese.txt", text.encode("utf-8"))
        got = ingest.read_any(p)
        self.assertEqual(got.text, text)
        self.assertEqual(got.dropped, 0)
        self.assertGreater(len(set(got.text)), 1000,
                           "the whole point of a Chinese corpus is its alphabet")

    def test_either_one_saved_as_utf16_is_the_same_corpus(self):
        """A Japanese or Chinese file off a Windows machine is the worst case:
        under errors="ignore" almost nothing survives AND the alphabet changes."""
        for name, text in (("ar.txt", arabic_corpus()),
                           ("zh.txt", chinese_corpus(700))):
            p = self.write(name, text.encode("utf-16"))
            got = ingest.read_any(p)
            self.assertEqual(got.text, text, f"{name} did not survive UTF-16")
            self.assertEqual(len(set(got.text)), len(set(text)),
                             f"{name} lost characters out of its alphabet")

    def test_a_multibyte_file_is_not_refused_by_the_cheap_check(self):
        """can_train_on reads a fixed probe, and with three-byte characters that
        boundary is almost never a character boundary — the case
        trim_to_char_boundary exists for, asked here through the picker's door."""
        p = self.write("zh.txt", chinese_corpus().encode("utf-8"))
        self.assertTrue(ingest.can_train_on(p))


class AccentsSurviveALegacyEncoding(Fixtures, unittest.TestCase):
    """cp1252, counted before and after."""

    def setUp(self):
        super().setUp()
        self.p = self.write("letter.txt", CP1252_LETTER.encode("cp1252"))

    def test_every_accented_character_comes_back(self):
        got = ingest.read_any(self.p)
        self.assertEqual(got.encoding, "cp1252")
        self.assertEqual(got.text, CP1252_LETTER)
        before = [c for c in CP1252_LETTER if ord(c) > 127]
        after = [c for c in got.text if ord(c) > 127]
        self.assertEqual(len(after), len(before))
        self.assertEqual(set(after), set(before))
        self.assertEqual(got.dropped, 0)

    def test_the_red_witness_deleted_all_of_them(self):
        loose = self.p.read_text(encoding="utf-8", errors="ignore")
        self.assertEqual([c for c in loose if ord(c) > 127], [],
                         "errors='ignore' deleted every accent in silence")
        self.assertIn("Caf au lait", loose,
                      "and left a sentence that still reads like a sentence")
        before = [c for c in CP1252_LETTER if ord(c) > 127]
        self.assertEqual(len(loose), len(CP1252_LETTER) - len(before),
                         "exactly the accented characters went, and nothing "
                         "anywhere said how many")


class WhatIsRefusedAndHowItIsSaid(Fixtures, unittest.TestCase):
    """A refusal is only worth having if the sentence tells somebody what to do."""

    def test_random_bytes_with_a_nul_are_refused(self):
        # A fixed seed rather than os.urandom: a test that reads differently on
        # two runs cannot be argued about. The first four bytes are the ones
        # cp1252 leaves "#UNDEFINED" (unicode.org/Public/MAPPINGS/VENDORS/MICSFT
        # /WINDOWS/CP1252.TXT), so neither rung of the ladder can claim it.
        import random
        rng = random.Random(20260921)
        blob = bytearray(rng.randrange(256) for _ in range(4096))
        blob[0:4] = b"\x8d\x81\x8f\x90"
        blob[100] = 0
        p = self.write("noise.txt", bytes(blob))
        got = ingest.read_any(p)
        self.assertIsNone(got.text, "random bytes were accepted as text")
        self.assertEqual(got.kind, "refused")
        self.assertEqual(got.encoding, "")
        self.assertIn("noise.txt", got.say.why)
        self.assertGreater(got.dropped, 0,
                           "a refusal should say how much is not characters")
        self.assertTrue(got.say.why.rstrip().endswith("."),
                        "a refusal is a sentence, not a label")
        self.assertFalse(ingest.can_train_on(p))

    def test_a_pdf_is_refused_under_either_name(self):
        for name in ("report.pdf", "notes.txt"):
            p = self.write(name, PDF_BYTES)
            got = ingest.read_any(p)
            self.assertIsNone(got.text, f"{name} was accepted as prose")
            self.assertIn("PDF", got.say.why)
            self.assertIn(".txt", got.say.why, "the sentence says what to do")
            self.assertFalse(ingest.can_train_on(p))

    def test_a_file_that_is_only_a_byte_order_mark_is_called_empty(self):
        """What a Save as box writes for an empty document.

        The size guard cannot catch it — there are bytes — and before the text
        rule was given this case first it refused a 3-byte file as "mostly
        characters that cannot be printed, which is what a compressed file looks
        like", about a file with no characters in it at all.
        """
        for name, mark in (("u8.txt", codecs.BOM_UTF8),
                           ("u16.txt", codecs.BOM_UTF16_LE)):
            got = ingest.read_any(self.write(name, mark))
            self.assertIsNone(got.text)
            self.assertEqual(got.say.word, "Empty")
            self.assertNotIn("compressed", got.say.why)

    def test_a_declared_encoding_that_breaks_is_called_damaged(self):
        """A UTF-16 file one byte short, which is what a failed download leaves.

        The number in the sentence has to be measured against the codec the FILE
        named. It was not: the old sentence said "2 of its bytes are not
        characters", the two being the mark, because every other byte of an
        English UTF-16 file is ASCII or NUL and UTF-8 decodes both.
        """
        data = ENGLISH.encode("utf-16")[:-1]
        got = ingest.read_any(self.write("cut.txt", data))
        self.assertIsNone(got.text)
        self.assertEqual(got.say.word, "Damaged")
        self.assertIn("utf-16", got.say.why)
        self.assertIn(f"{len(data):,}", got.say.why,
                      "the sentence says how far it got and how big it is")
        self.assertLess(got.dropped, 10,
                        "one truncated character, not the whole file")
        self.assertGreater(got.dropped, 0)


class ZipContainersGiveUpTheirText(Fixtures, unittest.TestCase):
    """.docx and .epub, assembled here rather than mocked."""

    def test_a_docx_gives_back_its_paragraphs_tabs_and_hyphens(self):
        p = self.tmp / "report.docx"
        want = word_docx(p)
        got = ingest.read_any(p)
        self.assertEqual(got.kind, "docx")
        self.assertEqual(got.text, want)
        self.assertIn("\t", got.text, "w:tab is a character the author typed")
        self.assertIn("‑", got.text, "w:noBreakHyphen was dropped")
        self.assertEqual(got.dropped, 0)

    def test_an_epub_gives_back_the_spine_and_not_the_zip_listing(self):
        p = self.tmp / "book.epub"
        epub_book(p)
        got = ingest.read_any(p)
        self.assertEqual(got.kind, "epub")
        self.assertIn("It opens on a cold morning.", got.text)
        self.assertIn("Grüße", got.text)
        self.assertNotIn("SCRIPT TEXT", got.text,
                         "a page's JavaScript is not prose")
        self.assertNotIn("LEFTOVER", got.text,
                         "the spine is the book; the listing is the box")

    def test_a_docx_that_is_not_a_zip_says_so(self):
        p = self.write("renamed.docx", b"just words, not an archive")
        got = ingest.read_any(p)
        self.assertIsNone(got.text)
        self.assertEqual(got.say.word, "Damaged")


class WhatTheAlphabetJudgementSays(unittest.TestCase):
    """say_vocabulary has to be useful on Chinese and quiet on English."""

    def test_chinese_gets_a_warning_with_numbers_in_it(self):
        say = ingest.say_vocabulary(chinese_corpus())
        self.assertEqual(say.tone, "unsettled")
        self.assertIn("large alphabet", say.why)
        self.assertIn(str(ingest.RARE_BELOW), say.why,
                      "the threshold is named, so the number can be checked")
        self.assertGreater(len(say.why), 120, "it says what the cost is")

    def test_english_is_not_nagged(self):
        say = ingest.say_vocabulary(ENGLISH)
        self.assertEqual(say.mark, look.PROVED)
        self.assertEqual(say.tone, "proved")
        self.assertIn("ordinary alphabet", say.why)

    def test_arabic_is_not_nagged_either(self):
        """41 distinct characters: an abjad is a small alphabet, not a big one."""
        say = ingest.say_vocabulary(arabic_corpus())
        self.assertEqual(say.mark, look.PROVED)

    def test_the_threshold_is_make_corpus_s_and_the_boundary_is_not_a_warning(self):
        at = "".join(chr(0x4E00 + i) for i in range(ingest.VOCAB_WARN))
        self.assertEqual(ingest.say_vocabulary(at).mark, look.PROVED)
        over = at + chr(0x4E00 + ingest.VOCAB_WARN)
        self.assertEqual(ingest.say_vocabulary(over).tone, "unsettled")


class OffThread:
    """The three attributes home.Home._read_text may touch.

    Copied deliberately rather than imported from test_home.py: a test file that
    imports another test file fails for reasons that have nothing to do with
    either of them. If _read_text ever grows a widget call, this stops being
    enough and that is the point — docs.python.org/3/library/tkinter.html
    #threading-model says such a call fails outright when the event loop is not
    running.
    """

    def __init__(self, tools=None, studio=None):
        self.q: queue.Queue = queue.Queue()
        self.tools = tools
        self.studio = studio

    def read(self, path):
        home.Home._read_text(self, ingest, pathlib.Path(path), False, 1, True)
        return self.q.get_nowait()[1]


class WhatTheFrontPageSaysAboutAScript(Fixtures, unittest.TestCase):
    """The two things step 1 puts on screen about an encoding.

    Neither of these opens a window. The facts line is a pure function and the
    reader is called off the Tk thread by construction, which is the only
    configuration this machine and CI share.
    """

    def test_the_card_claims_the_read_when_the_corpus_check_cannot_run(self):
        """With no torch, data.py and leakage.py do not import, so load_tools
        returns None and measure_text can only answer "Not checked". That is not
        a stronger claim than the read; it is no claim, and it used to be what a
        perfectly read Arabic corpus got — a grey dash and a sentence about a
        repetition check that never happened.
        """
        text = arabic_corpus()
        p = self.write("arabic.txt", text.encode("utf-8"))
        m = OffThread(tools=None).read(p)
        self.assertTrue(m["accepted"])
        say = home.as_say(m["say"])
        self.assertEqual(say.mark, look.PROVED,
                         "a file that was read properly is not an open question")
        self.assertIn("arabic.txt", say.why)
        self.assertIn(f"{len(text):,}", say.why)
        self.assertEqual(m["distinct"], len(set(text)))

    def test_a_corpus_check_that_ran_still_wins(self):
        class Tools:
            def group_split(self, t):
                return t[:len(t) // 2], t[len(t) // 2:]

            def scan(self, tr, va, doc_aligned=False):
                return type("R", (), {"verdict": "CLEAN", "trustworthy": True})()

            def split_health(self, t):
                return {"achievable_val_frac": 0.2, "requested_val_frac": 0.1,
                        "achieved_val_frac": 0.15, "unique_documents": 9,
                        "largest_unique_doc_frac": 0.2}

            def split_verdict(self, h):
                return None

            def documents(self, t):
                return ["a"] * 9

        p = self.write("arabic.txt", arabic_corpus().encode("utf-8"))
        m = OffThread(tools=Tools()).read(p)
        self.assertNotIn("characters out of", home.as_say(m["say"]).why,
                         "the corpus verdict, not the read, is the claim here")

    def test_the_facts_line_names_every_encoding_in_words(self):
        """A codec name on the front page is a term from the underlying system,
        which developer.gnome.org/hig/guidelines/writing-style.html says not to
        use. utf-8-sig was the one that got through."""
        for encoding in ("utf-16 (BOM)", "utf-8-sig (BOM)", "cp1252",
                         "utf-32 (BOM)"):
            note = home.encoding_note(encoding)
            self.assertTrue(note, f"{encoding} got no sentence")
            self.assertNotIn("utf-8-sig", note)
            self.assertNotIn("cp1252", note.replace(
                "cp1252, the single-byte Windows encoding for western Europe",
                ""), "cp1252 is named, but in words as well")
        self.assertEqual(home.encoding_note("utf-8"), "",
                         "plain UTF-8 is the common case and needs no sentence")

    def test_the_facts_line_carries_the_counts_and_the_encoding_together(self):
        facts = home.text_facts(2520, 42, None, None, "utf-8-sig (BOM)")
        self.assertIn("2,520 characters", facts)
        self.assertIn("42 different characters", facts)
        self.assertIn("BOM", facts)


class AFolderOfDifferentScripts(Fixtures, unittest.TestCase):
    """read_corpus over a folder holding Arabic, Chinese, English and a PDF."""

    def setUp(self):
        super().setUp()
        self.ar = arabic_corpus()
        self.zh = chinese_corpus(700)
        self.write("a-arabic.txt", self.ar.encode("utf-8"))
        self.write("b-chinese.txt", self.zh.encode("utf-8"))
        self.write("c-english.txt", ENGLISH.encode("utf-16"))
        self.write("d-report.pdf", PDF_BYTES)

    def test_the_text_files_are_joined_and_the_pdf_is_left_out(self):
        got = ingest.read_corpus([self.tmp])
        self.assertIsNotNone(got.text)
        self.assertEqual(got.dropped, 0)
        for piece in (self.ar, self.zh, ENGLISH):
            self.assertIn(piece, got.text, "a whole file went missing")
        self.assertNotIn("%PDF", got.text)
        self.assertIn("1 other file", got.say.why,
                      "what was left out is said, not hidden")

    def test_mixed_encodings_are_named_rather_than_guessed_at(self):
        got = ingest.read_corpus([self.tmp])
        self.assertEqual(got.encoding, "mixed encodings",
                         "no single encoding is a fact about this corpus")
        self.assertTrue(home.encoding_note(got.encoding),
                        "and the front page still has a sentence for it")


if __name__ == "__main__":
    unittest.main(verbosity=2)
