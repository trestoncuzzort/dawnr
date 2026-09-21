"""Can this read a file somebody actually has, or only the one we tested with?

THE RED WITNESS, on the line ingest.py replaced. Files a person really owns,
read the old way — `read_text(encoding="utf-8", errors="ignore")` — and then
through read_any. Measured on this machine, 2026-09-21:

    notes.txt, 2,760 characters of English saved as UTF-16 from a Windows
    Save as box
        old:  5,520 characters, 2,736 of them NUL: the text with a NUL wedged
              between every character, and NUL added to the alphabet
        new:  2,760 characters, exactly the file, "utf-16 (BOM)"
    the same file in Japanese, 760 characters over an alphabet of 18
        old:  1,280 characters of mojibake; 1 of the 18 survives
        new:  760 characters, exactly the file
    letter.txt, 920 characters saved as cp1252
        old:  740 characters — all 180 accented ones deleted in silence,
              "Café au lait" arriving as "Caf au lait"
        new:  920 characters, every accent intact, "cp1252"
    report.pdf, 1,088 bytes
        old:  576 characters of printer instructions accepted as prose
        new:  refused, and the sentence says PDF
    notes.rtf
        old:  accepted whole, including 6 control words — \\rtf1, \\fonttbl,
              \\par went into the corpus as though they were words
        new:  refused, and the sentence says what to save it as instead

Every one of those is a file a stranger would call a text file. In a
character-level model the corpus IS the vocabulary, so a dropped character is
not a cosmetic loss and an accepted control word is a permanent entry in the
alphabet the model writes with.

THE PROPERTY THAT MATTERS MOST is the last test here rather than any one case:
on every accept, `dropped == 0`. There is no third answer where a partly
decoded string reaches a tokenizer.

No torch and no display: this is the configuration this machine and CI share.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ingest  # noqa: E402
import look  # noqa: E402
import make_corpus  # noqa: E402


def _write(tmp: pathlib.Path, name: str, data: bytes) -> pathlib.Path:
    p = tmp / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


# --------------------------------------------------------------------------
# FIXTURES BUILT HERE, not checked in. A .docx in the repository is a binary
# blob nobody can review in a diff; a .docx built in eleven lines of zipfile is
# a fixture whose every byte is visible in this file.
# --------------------------------------------------------------------------
DOCX_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t xml:space="preserve">Dear Mrs Okonkwo,</w:t></w:r></w:p>
    <w:p><w:r><w:t xml:space="preserve">The pump ran at 88.4</w:t></w:r>
         <w:r><w:t xml:space="preserve">°C all night.</w:t></w:r></w:p>
    <w:p><w:r><w:t>Column one</w:t><w:tab/><w:t>column two</w:t></w:r></w:p>
  </w:body>
</w:document>"""

DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Target="{target}"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>
</Relationships>"""


def _docx(tmp: pathlib.Path, name: str = "chapter.docx",
          part: str = "word/document.xml") -> pathlib.Path:
    p = tmp / name
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("_rels/.rels", DOCX_RELS.format(target=part))
        z.writestr(part, DOCX_XML)
    return p


EPUB_CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/book.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

EPUB_OPF = """<?xml version="1.0"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>A Book</dc:title></metadata>
  <manifest>
    <item id="one" href="one.xhtml" media-type="application/xhtml+xml"/>
    <item id="two" href="two.xhtml" media-type="application/xhtml+xml"/>
    <item id="left-out" href="notused.xhtml" media-type="application/xhtml+xml"/>
    <item id="cover" href="cover.png" media-type="image/png"/>
  </manifest>
  <spine>
    <itemref idref="one"/>
    <itemref idref="two"/>
    <itemref idref="cover"/>
  </spine>
</package>"""

EPUB_CHAPTER = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title>
<style>p {{ margin: 0 }}</style></head>
<body><h1>{title}</h1><p>{body}</p></body></html>"""


def _epub(tmp: pathlib.Path, name: str = "book.epub") -> pathlib.Path:
    p = tmp / name
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", EPUB_CONTAINER)
        z.writestr("OEBPS/book.opf", EPUB_OPF)
        z.writestr("OEBPS/one.xhtml",
                   EPUB_CHAPTER.format(title="Chapter one", body="It was a dark night."))
        z.writestr("OEBPS/two.xhtml",
                   EPUB_CHAPTER.format(title="Chapter two", body="Then the morning came."))
        z.writestr("OEBPS/notused.xhtml",
                   EPUB_CHAPTER.format(title="Draft", body="AN EARLIER EDITION"))
        z.writestr("OEBPS/cover.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00")
    return p


HTML_PAGE = b"""<!doctype html><html><head><title>Pump log</title>
<style>body { color: #ff0000; background: url(x.png) }</style>
<script>var secret = 1; function alertOperator() { alert("overtemp"); }</script>
</head><body>
<h1>Pump log</h1>
<p>The pump ran at 88.4&deg;C.</p>
<p>It was shut down at midnight.</p>
<script>document.write("injected");</script>
</body></html>"""


class Encodings(unittest.TestCase):
    """The ladder, one rung at a time."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def test_a_utf16_file_with_a_bom_decodes_to_exactly_the_right_string(self):
        """The worst bug, and the most ordinary file.

        UTF-16 LE is one of the five entries in Notepad's Save as list, so this
        is not an exotic case — it is what somebody gets by picking the line
        next to the one they meant.
        """
        original = "ある日、森の中で。The quick brown fox. Grüße! " * 40
        p = _write(self.tmp, "notes.txt", original.encode("utf-16"))

        got = ingest.read_any(p)
        self.assertEqual(got.text, original, "the file did not come back whole")
        self.assertEqual(got.dropped, 0)
        self.assertEqual(got.kind, "text")
        self.assertIn("utf-16", got.encoding.lower())
        self.assertIn("BOM", got.encoding)

        # RED WITNESS on these same bytes, so this test cannot pass against the
        # line it replaced. Two separate harms, and the first one surprises
        # people: the old read is not SHORT, it is longer than the file, because
        # a NUL byte is perfectly good UTF-8 and errors="ignore" keeps every one
        # of them. In a character model that is one more row of the embedding
        # table, learned from half the corpus.
        mangled = p.read_text(encoding="utf-8", errors="ignore")
        self.assertNotEqual(mangled, original)
        self.assertIn("\x00", mangled,
                      "errors='ignore' kept the padding bytes as NUL characters")
        self.assertNotIn("ある日", mangled,
                         "the fixture no longer loses the text it is about")

    def test_utf16_big_endian_is_read_too(self):
        original = "Grüße aus München. " * 10
        p = _write(self.tmp, "be.txt", ingest.codecs.BOM_UTF16_BE
                   + original.encode("utf-16-be"))
        got = ingest.read_any(p)
        self.assertEqual(got.text, original)
        self.assertEqual(got.dropped, 0)

    def test_the_utf8_bom_does_not_survive_into_the_text(self):
        """utf-8-sig, whose whole job is that the mark is not a character.

        A surviving U+FEFF is not cosmetic here: it would be one more row of the
        embedding table, learned from one example, at the start of the corpus.
        """
        original = "# Notes\nordinary prose\n"
        p = _write(self.tmp, "bom.md",
                   ingest.codecs.BOM_UTF8 + original.encode("utf-8"))
        got = ingest.read_any(p)
        self.assertEqual(got.text, original)
        self.assertNotIn("﻿", got.text)
        self.assertEqual(got.dropped, 0)

    def test_utf32_is_not_mistaken_for_utf16(self):
        """BOM_UTF32_LE starts with BOM_UTF16_LE, so order is the whole test.

        Tested against the wrong mark first, this file decodes into a string of
        NULs rather than failing — which is the quiet kind of wrong.
        """
        original = "quarterly figures, in four-byte characters\n"
        p = _write(self.tmp, "wide.txt", original.encode("utf-32"))
        got = ingest.read_any(p)
        self.assertEqual(got.text, original)
        self.assertIn("utf-32", got.encoding)
        self.assertEqual(ingest.BOMS[0][0], ingest.codecs.BOM_UTF32_LE,
                         "the longest byte order mark is no longer tried first")

    def test_a_cp1252_file_keeps_every_accent(self):
        """The file that came off an older Windows machine.

        Under errors="ignore" each accented character is simply deleted: "café"
        becomes "caf". Here the whole string has to come back, byte for byte.
        """
        original = ("Café au lait, 5 £, naïve résumé — “quoted” and ‘quoted’, "
                    "Grüße, Ærø, 30°C\n" * 8)
        p = _write(self.tmp, "letter.txt", original.encode("cp1252"))
        got = ingest.read_any(p)
        self.assertEqual(got.text, original, "an accented character was lost")
        self.assertEqual(got.encoding, "cp1252")
        self.assertEqual(got.dropped, 0)
        for accent in "éïüÆø£°—“‘":
            self.assertIn(accent, got.text)
        # RED WITNESS on the same bytes. The count is not asserted, because how
        # many characters errors="ignore" eats depends on which accented bytes
        # happen to sit next to each other — what is asserted is the shape of
        # the loss, which does not depend on the fixture: the prose survives and
        # every accent in it is gone.
        mangled = p.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("Caf au lait", mangled)
        self.assertLess(len(mangled), len(original))
        self.assertEqual(set(mangled) & set("éïüÆø£°—“‘"), set(),
                         "the fixture no longer loses its accents the old way")

    def test_a_latin1_file_decodes_through_the_cp1252_rung(self):
        """cp1252 and latin-1 agree on every byte from 0xA0 to 0xFF.

        That is why one rung covers both, and the test checks the claim rather
        than repeating it: all 96 of those bytes must decode identically.
        """
        pairs = [(bytes([b]).decode("cp1252"), bytes([b]).decode("latin-1"))
                 for b in range(0xA0, 0x100)]
        self.assertTrue(all(a == b for a, b in pairs),
                        "cp1252 and latin-1 no longer agree over 0xA0-0xFF")
        original = "Grüße, café, naïve\n" * 5
        p = _write(self.tmp, "old.txt", original.encode("latin-1"))
        self.assertEqual(ingest.read_any(p).text, original)

    def test_latin1_is_not_in_the_ladder_because_it_can_never_fail(self):
        """An encoding that refuses nothing does not add a fallback — it
        deletes the refusal."""
        for name in ingest.NEVER_GUESSED:
            refused = [b for b in range(256)
                       if _refuses(bytes([b]), name)]
            self.assertEqual(refused, [],
                             f"{name} refuses bytes, so the reason it is "
                             f"excluded no longer holds")
            self.assertNotIn(name, ingest.LEGACY_ENCODINGS)
        # And the rung that IS used is falsifiable: five byte values, the ones
        # unicode.org's CP1252.TXT marks UNDEFINED.
        undefined = [b for b in range(256) if _refuses(bytes([b]), "cp1252")]
        self.assertEqual(undefined, [0x81, 0x8D, 0x8F, 0x90, 0x9D])

    def test_random_bytes_with_a_nul_are_refused_and_text_is_none(self):
        noise = bytes(range(256)) * 8
        self.assertIn(b"\x00", noise)
        p = _write(self.tmp, "blob.dat", noise)
        got = ingest.read_any(p)
        self.assertIsNone(got.text, "binary was accepted as text")
        self.assertEqual(got.kind, "refused")
        self.assertEqual(got.encoding, "")
        self.assertGreater(got.dropped, 0,
                           "a refusal that counts nothing cannot say how much "
                           "of the file is not text")
        self.assertIn("utf-8", got.say.why, "the refusal does not say what was tried")

    def test_a_refusal_never_returns_half_a_string(self):
        """Valid UTF-8 for 4 kB, then bytes that are not characters at all."""
        p = _write(self.tmp, "half.txt",
                   ("readable prose " * 300).encode("utf-8") + b"\xff\xfe\xfd" * 200
                   + b"\x00")
        got = ingest.read_any(p)
        self.assertIsNone(got.text,
                          "the readable half was returned as if it were the file")


def _refuses(data: bytes, encoding: str) -> bool:
    try:
        data.decode(encoding)
        return False
    except UnicodeDecodeError:
        return True


class Formats(unittest.TestCase):
    """Containers, with the standard library and nothing else."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def test_a_docx_gives_up_its_text(self):
        got = ingest.read_any(_docx(self.tmp))
        self.assertIsNotNone(got.text)
        self.assertEqual(got.kind, "docx")
        self.assertEqual(got.dropped, 0)
        self.assertIn("Dear Mrs Okonkwo,", got.text)
        self.assertIn("88.4°C", got.text, "two runs of one sentence were not joined")
        self.assertIn("Column one\tcolumn two", got.text, "w:tab became nothing")
        self.assertNotIn("Okonkwo,The", got.text,
                         "two paragraphs were welded into one word")
        self.assertIn("characters out of", got.say.why)
        self.assertIn("Word document", got.say.why,
                      "the sentence does not say where the characters came from")

    def test_a_docx_whose_part_is_not_called_word_document_xml(self):
        """The main part is found through the package relationships.

        Assuming the conventional name works for Word's own output and fails
        for a document produced by anything else.
        """
        p = _docx(self.tmp, name="odd.docx", part="parts/main.xml")
        got = ingest.read_any(p)
        self.assertIsNotNone(got.text, f"refused: {got.say.why}")
        self.assertIn("Dear Mrs Okonkwo,", got.text)

    def test_an_epub_gives_up_its_chapters_in_spine_order(self):
        got = ingest.read_any(_epub(self.tmp))
        self.assertIsNotNone(got.text, f"refused: {got.say.why}")
        self.assertEqual(got.kind, "epub")
        self.assertEqual(got.dropped, 0)
        self.assertIn("It was a dark night.", got.text)
        self.assertIn("Then the morning came.", got.text)
        self.assertLess(got.text.index("dark night"), got.text.index("morning came"),
                        "the chapters came back out of reading order")
        self.assertNotIn("AN EARLIER EDITION", got.text,
                         "a manifest item that is not in the spine was read")
        self.assertNotIn("margin", got.text, "the chapter's CSS reached the text")

    def test_html_leaves_the_script_and_the_style_behind(self):
        p = _write(self.tmp, "page.html", HTML_PAGE)
        got = ingest.read_any(p)
        self.assertIsNotNone(got.text, f"refused: {got.say.why}")
        self.assertEqual(got.kind, "html")
        self.assertEqual(got.dropped, 0)
        self.assertIn("The pump ran at 88.4°C.", got.text)
        self.assertIn("shut down at midnight", got.text)
        for junk in ("var secret", "alertOperator", "document.write", "injected",
                     "#ff0000", "background", "url(x.png)"):
            self.assertNotIn(junk, got.text,
                             f"“{junk}” came out of a script or style element")
        self.assertNotIn("88.4°C.It was", got.text,
                         "two paragraphs were welded into one word")

    def test_html_honours_the_encoding_the_page_declares(self):
        """A saved page that says what it is, in the first 1024 bytes."""
        body = ('<html><head><meta charset="windows-1252"></head>'
                '<body><p>Café — naïve</p></body></html>')
        p = _write(self.tmp, "declared.html", body.encode("cp1252"))
        got = ingest.read_any(p)
        self.assertIsNotNone(got.text, f"refused: {got.say.why}")
        self.assertIn("Café — naïve", got.text)

    def test_a_pdf_is_refused_with_a_sentence_naming_pdf(self):
        p = _write(self.tmp, "report.pdf", b"%PDF-1.7\n" + bytes(range(256)) * 8)
        got = ingest.read_any(p)
        self.assertIsNone(got.text)
        self.assertEqual(got.kind, "refused")
        self.assertIn("PDF", got.say.why)
        self.assertIn(".txt", got.say.why, "the refusal does not say what to do")

    def test_a_pdf_is_refused_even_when_it_is_called_something_else(self):
        """The name is a claim by whoever saved it; the first five bytes are not."""
        p = _write(self.tmp, "notes.txt", b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nstream\n")
        got = ingest.read_any(p)
        self.assertIsNone(got.text)
        self.assertIn("PDF", got.say.why)

    def test_rtf_is_refused_rather_than_let_through_as_prose(self):
        """THE TRAP THE AUDIT FOUND. An RTF file is 7-bit ASCII, so the text
        rule accepted it and its control words went into the corpus as words."""
        rtf = (rb"{\rtf1\ansi\deff0{\fonttbl{\f0\froman Times;}}"
               rb"\pard\qc\b Quarterly report\b0\par Sales rose 4 per cent.\par}")
        p = _write(self.tmp, "notes.rtf", rtf)
        got = ingest.read_any(p)
        self.assertIsNone(got.text, "RTF control words reached the corpus")
        self.assertIn("Rich Text", got.say.why)
        # The red witness: the rule that used to decide is still happy with it.
        self.assertTrue(make_corpus.looks_like_text(rtf),
                        "the fixture no longer reproduces the trap")

    def test_a_renamed_zip_is_refused_as_damaged_not_as_a_word_document(self):
        p = _write(self.tmp, "fake.docx", b"this is not a zip at all")
        got = ingest.read_any(p)
        self.assertIsNone(got.text)
        self.assertIn("zip", got.say.why)


class SizeGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def test_the_cheap_check_costs_no_read(self):
        p = _write(self.tmp, "small.txt", b"ordinary prose\n")
        self.assertEqual(ingest.size_of(p), 15)
        self.assertEqual(ingest.check_size(p).mark, look.PROVED)
        self.assertEqual(ingest.size_of(self.tmp / "nothing.txt"), -1)
        self.assertEqual(ingest.check_size(self.tmp / "nothing.txt").mark,
                         look.REFUTED)

    def test_a_file_over_the_ceiling_is_refused_before_it_is_read(self):
        p = _write(self.tmp, "big.txt", b"x" * 4096)
        got = ingest.read_any(p, max_bytes=900)
        self.assertIsNone(got.text)
        self.assertIn("4 kB", got.say.why, "the refusal does not say how big it is")
        self.assertIn("900 bytes", got.say.why,
                      "the refusal does not say what the ceiling is")
        # And the same file under the ceiling reads normally, so the guard is a
        # ceiling rather than a refusal of large-ish files.
        self.assertIsNotNone(ingest.read_any(p, max_bytes=8192).text)

    def test_the_thresholds_are_in_the_order_they_are_documented(self):
        self.assertLess(ingest.WARN_BYTES, ingest.MAX_BYTES)
        self.assertEqual(ingest.check_size(__file__).word, "Fits")


class CheapCheck(unittest.TestCase):
    """can_train_on has to agree with read_any, or a picker hides the file."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def test_it_agrees_with_read_any_on_every_case_here(self):
        cases = {
            "plain.txt": (b"ordinary prose\n", True),
            "NOEXTENSION": (b"a file with no extension at all\n", True),
            "sensor.csv": (b"ts,temp\n2026-07-30,88.4\n", True),
            "utf16.txt": ("Windows wrote this".encode("utf-16"), True),
            "cp1252.txt": ("café naïve\n".encode("cp1252"), True),
            "photo.png": (b"\x89PNG\r\n\x1a\n\x00\x00\x00IHDR", False),
            "report.pdf": (b"%PDF-1.7\nstream\n", False),
            "notes.rtf": (rb"{\rtf1\ansi hello\par}", False),
            "blob.dat": (bytes(range(256)) * 8, False),
        }
        wrong = []
        for name, (data, want) in cases.items():
            p = _write(self.tmp, name, data)
            cheap = ingest.can_train_on(p)
            full = ingest.read_any(p).text is not None
            if cheap is not want:
                wrong.append(f"{name}: can_train_on={cheap}, expected {want}")
            if cheap != full:
                wrong.append(f"{name}: can_train_on={cheap} but read_any={full}")
        self.assertEqual(wrong, [], "the cheap check and the real one disagree")

    def test_a_utf16_file_is_not_hidden_by_the_picker(self):
        """The rule that used to decide says no to this file, and it is text.

        `looks_like_text` decodes as UTF-8 and refuses anything holding a NUL
        byte, which is right for the question make_corpus was asking and wrong
        for a picker: every UTF-16 file is full of NUL bytes by design. So the
        old rule greys out exactly the file this round exists to accept.

        make_corpus.is_trainable_file now asks can_train_on for the content
        half rather than keeping its own answer, so the two agree here by
        construction — which is what the second assertion pins.
        """
        p = _write(self.tmp, "notes.txt", "Windows wrote this".encode("utf-16"))
        self.assertFalse(make_corpus.looks_like_text(p.read_bytes()),
                         "the fixture no longer exercises the disagreement")
        self.assertTrue(ingest.can_train_on(p))
        self.assertTrue(make_corpus.is_trainable_file(p)[0],
                        "make_corpus and the picker disagree about one file")

    def test_containers_are_offered_although_their_names_say_binary(self):
        self.assertIn(".docx", make_corpus.BINARY_EXTS)
        self.assertTrue(ingest.can_train_on(_docx(self.tmp)))
        self.assertTrue(ingest.can_train_on(_epub(self.tmp)))

    def test_a_missing_file_is_a_no_rather_than_a_crash(self):
        self.assertFalse(ingest.can_train_on(self.tmp / "nothing.txt"))
        self.assertFalse(ingest.can_train_on(self.tmp))


class Corpus(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def test_a_folder_is_read_and_what_is_not_text_is_counted_not_fatal(self):
        folder = self.tmp / "letters"
        _write(folder, "a.txt", "one two three".encode("utf-8"))
        _write(folder, "b.txt", "four five six".encode("utf-16"))
        _write(folder, "photo.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00")
        got = ingest.read_corpus([folder])
        self.assertIsNotNone(got.text, f"refused: {got.say.why}")
        self.assertIn("one two three", got.text)
        self.assertIn("four five six", got.text)
        self.assertEqual(got.dropped, 0)
        self.assertEqual(got.encoding, "mixed encodings",
                         "two encodings were reported as one")
        self.assertIn("2 files", got.say.why)
        self.assertIn("left out", got.say.why, "the photograph was not accounted for")

    def test_a_folder_with_nothing_readable_in_it_is_refused(self):
        folder = self.tmp / "photos"
        _write(folder, "a.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00")
        _write(folder, "b.png", b"\x89PNG\r\n\x1a\n\x00\x00\x01")
        got = ingest.read_corpus([folder])
        self.assertIsNone(got.text)
        self.assertEqual(got.kind, "refused")

    def test_nothing_is_invented_between_the_documents(self):
        """Every character this file writes is a character the model learns."""
        folder = self.tmp / "two"
        _write(folder, "a.txt", b"one")
        _write(folder, "b.txt", b"two")
        got = ingest.read_corpus([folder])
        self.assertEqual(got.text, "one\n\ntwo")


class Vocabulary(unittest.TestCase):
    """make_corpus.py:242's warning, in the shape a window can show."""

    def test_it_fires_above_three_hundred_and_not_below(self):
        self.assertEqual(ingest.VOCAB_WARN, 300,
                         "the threshold is make_corpus.py:242's and did not move")
        small = "".join(chr(0x4E00 + i) for i in range(ingest.VOCAB_WARN))
        big = "".join(chr(0x4E00 + i) for i in range(ingest.VOCAB_WARN + 1))
        self.assertEqual(len(set(small)), 300)

        quiet = ingest.say_vocabulary(small)
        self.assertEqual(quiet.mark, look.PROVED)
        self.assertEqual(quiet.tone, "proved")

        loud = ingest.say_vocabulary(big)
        self.assertEqual(loud.tone, "unsettled")
        self.assertIn("301", loud.why)
        self.assertIn("cannot be learned", loud.why,
                      "the sentence no longer says why a big alphabet costs")

    def test_it_counts_the_characters_that_are_too_rare_to_learn(self):
        text = ("the quick brown fox " * 500) + "".join(
            chr(0x4E00 + i) for i in range(400))
        say = ingest.say_vocabulary(text)
        self.assertIn("400", say.why, "the rare characters were not counted")


ACCEPTS = "a table of every kind of accept, so the property below covers them all"


class TheContract(unittest.TestCase):
    """The shape every caller is written against."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        folder = self.tmp / "folder"
        _write(folder, "a.txt", b"one two three")
        _write(folder, "b.txt", b"four five six")
        self.cases = {
            "utf-8": (_write(self.tmp, "plain.txt", "prose\n".encode("utf-8")), "text"),
            "utf-8-sig": (_write(self.tmp, "bom.txt",
                                 ingest.codecs.BOM_UTF8 + b"prose\n"), "text"),
            "utf-16": (_write(self.tmp, "win.txt", "prose\n".encode("utf-16")), "text"),
            "utf-32": (_write(self.tmp, "wide.txt", "prose\n".encode("utf-32")), "text"),
            "cp1252": (_write(self.tmp, "old.txt", "café\n".encode("cp1252")), "text"),
            "csv": (_write(self.tmp, "s.csv", b"ts,temp\n1,88.4\n"), "text"),
            "no extension": (_write(self.tmp, "NOEXT", b"still text\n"), "text"),
            "docx": (_docx(self.tmp), "docx"),
            "epub": (_epub(self.tmp), "epub"),
            "html": (_write(self.tmp, "page.html", HTML_PAGE), "html"),
        }
        self.folder = folder

    def test_every_accept_drops_nothing(self):
        """THE PROPERTY, across the whole table, because it is the contract.

        If any path here could return text with characters missing from it, the
        rest of this file would be a collection of examples rather than a
        guarantee.
        """
        bad = []
        for label, (p, kind) in self.cases.items():
            got = ingest.read_any(p)
            if got.text is None:
                bad.append(f"{label}: refused — {got.say.why}")
                continue
            if got.dropped != 0:
                bad.append(f"{label}: dropped {got.dropped}")
            if got.kind != kind:
                bad.append(f"{label}: kind {got.kind!r}, expected {kind!r}")
            if not got.encoding:
                bad.append(f"{label}: accepted without naming an encoding")
        corpus = ingest.read_corpus([self.folder])
        if corpus.text is None or corpus.dropped != 0:
            bad.append(f"folder: {corpus.dropped} dropped, {corpus.say.why}")
        self.assertEqual(bad, [])

    def test_every_answer_comes_back_as_a_say_a_window_can_render(self):
        """home.py turns `tone` into a colour inside its message pump, whose
        only except is queue.Empty — so a tone that is not a palette key stops
        every later message on that page without printing a word."""
        answers = [ingest.read_any(p) for p, _ in self.cases.values()]
        answers.append(ingest.read_corpus([self.folder]))
        answers.append(ingest.read_any(self.tmp / "nothing-at-all.txt"))
        answers.append(ingest.read_any(self.tmp))
        for got in answers:
            say = got.say
            self.assertIn(say.mark, look.MARKS)
            self.assertIn(say.tone, look.PALETTES["light"])
            self.assertTrue(str(say.why).strip())
            self.assertTrue(str(say.word).strip())
            self.assertLessEqual(len(say.word.split()), 3,
                                 f"“{say.word}” is a sentence, not a headline")

    def test_a_refusal_is_a_read_and_never_an_exception(self):
        """Callers are written to check `text is None`, not to catch."""
        for p in (self.tmp / "nothing.txt", self.tmp, self.tmp / "nothing.docx"):
            got = ingest.read_any(p)
            self.assertIsNone(got.text)
            self.assertEqual(got.kind, "refused")
            self.assertEqual(got.dropped, 0)

    def test_the_three_names_the_other_files_import(self):
        for name in ("read_any", "can_train_on", "read_corpus", "Read"):
            self.assertTrue(hasattr(ingest, name), f"ingest.{name} is gone")
        self.assertEqual(ingest.Read._fields,
                         ("text", "kind", "encoding", "dropped", "say"))

    def test_nothing_in_here_decodes_with_ignore(self):
        """The error handler that is banned in every path a user's file travels.

        TOKENS, NOT A TEXT SEARCH. Searching the source for `errors="ignore"`
        matches this module's own prose about the rule, which is how that kind
        of test ends up being deleted for crying wolf. Every use of the handler
        needs the literal "ignore" as a string token of its own, so that is what
        is looked for — and the prose, which is one long docstring token, is
        invisible to it.

        Limit: a handler passed as a variable would not be caught. Nothing here
        does that, and a test that catches the way it was actually written
        twice in this repository is worth having.
        """
        import io
        import tokenize
        src = (HERE / "ingest.py").read_bytes()
        for tok in tokenize.tokenize(io.BytesIO(src).readline):
            if tok.type == tokenize.STRING and tok.string.strip() in (
                    '"ignore"', "'ignore'"):
                self.fail(f"ingest.py line {tok.start[0]} passes the \"ignore\" "
                          f"error handler: {tok.line.strip()}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
