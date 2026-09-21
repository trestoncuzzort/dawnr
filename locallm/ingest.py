"""ingest.py — the one thing allowed to read a file somebody else wrote.

THE RULE THIS FILE EXISTS FOR. `read_any` either decodes a file properly and
names the encoding that worked, or it refuses and says why in a sentence a
person can act on. There is no third answer. `errors="ignore"` is banned in
every path a user's own file travels, because a partly-decoded string is worse
than a refusal in exactly this program: the tokenizer IS the set of characters
in the corpus (see data.py), so every junk character that survives a sloppy
decode becomes a permanent row of the embedding table and a column of the
output layer.

WHAT IT REPLACED, measured on this machine 2026-09-21. Left column is
`read_text(encoding="utf-8", errors="ignore")`, the line that stood in
home.py, studio.py and start_studio.py; right column is read_any:

    notes.txt, 2,760 characters of English, saved as UTF-16 from a Windows
    Save as box
        old   5,520 characters, 2,736 of them NUL — the text with a NUL
              wedged between every character, and NUL added to the alphabet
        new   2,760 characters, exactly the file, encoding "utf-16 (BOM)"

    the same thing in Japanese, 760 characters over an alphabet of 18
        old   1,280 characters of mojibake; 1 of the 18 survives
        new   760 characters, exactly the file

    letter.txt, 920 characters in cp1252
        old   740 characters: all 180 accented ones deleted in silence,
              "Café au lait" arriving as "Caf au lait"
        new   920 characters, every accent intact, encoding "cp1252"

    report.pdf, 1,088 bytes
        old   576 characters of printer instructions, accepted as prose
        new   refused, in a sentence that says PDF and what to do instead

    notes.rtf
        old   accepted whole, control words and all: \\rtf1, \\fonttbl, \\par
              went into the corpus as though they were words
        new   refused, in a sentence that says what to save it as

THE CONTRACT, which several other files are written against and which nobody
may change:

    Read(text, kind, encoding, dropped, say)
    read_any(path)      -> Read      one file
    can_train_on(path)  -> bool      the cheap check a picker or drop target
                                     can afford before either
    read_corpus(paths)  -> Read      several files, or a folder, joined

`dropped` is 0 on every accept, by construction rather than by inspection:
nothing here can produce text with characters missing from it.

WHAT IS REUSED RATHER THAN REWRITTEN. make_corpus.py was hardened on 2026-09-20
and already owns the text rule: `text_is_readable` (no NUL, 90% printable),
`trim_to_char_boundary` (a fixed-size probe ends mid-character), `BINARY_EXTS`
and `SKIP_DIRS`. Those are imported, not copied. What is added here is
everything that happens BEFORE that rule can be applied — deciding which bytes
are characters at all.

IT MUST STAY IMPORTABLE IN A BARE PROCESS: standard library plus look.py and
make_corpus.py. No torch, no tkinter, no third-party parser. The dependency
claim this project makes to a stranger is "PyTorch and Tk", and a reader that
quietly needs python-docx or chardet breaks it.
"""
from __future__ import annotations

import codecs
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import NamedTuple
from urllib.parse import unquote

import look
from make_corpus import (BINARY_EXTS, SKIP_DIRS, text_is_readable,
                         trim_to_char_boundary)


class Read(NamedTuple):
    """One answer about one piece of somebody's text.

    text      the characters, or None when the file was refused. NEVER a string
              with characters missing from it.
    kind      "text", "docx", "epub", "html", or "refused" — where the
              characters came from, so a window can say "read 41,000 characters
              out of that .docx" rather than just "read 41,000 characters".
    encoding  what actually decoded it: "utf-8", "utf-16 (BOM)", "cp1252", or
              "" when nothing was decoded.
    dropped   characters that could not be decoded. 0 on any accept.
    say       a look.Say: mark, one word, one plain sentence, tone.
    """
    text: str | None
    kind: str
    encoding: str
    dropped: int
    say: object


# --------------------------------------------------------------------------
# THE SIZE GUARD. There was none anywhere, and both windows used to read whole
# files on the Tk thread.
#
# MEASURED HERE, 2026-09-21, on a 67.1 MB file of mixed Japanese, Cyrillic and
# Latin text:
#     read + strict decode   0.073 s   (916 MB/s, warm page cache)
#     counting its distinct characters, which both windows do next:  0.344 s
#     peak resident memory   2.34x the file size (1.91x for pure ASCII),
#                            because the bytes and the decoded string are both
#                            in hand at once
#
# So TIME is not what makes a big file dangerous on this machine — MEMORY is.
# 256 MiB of file is about 600 MB of resident memory before a single character
# is tokenised, on a laptop this is meant to run on unchanged. That is the
# ceiling, and it is ~275x the largest corpus this repository has ever trained
# on (926 KB, t/runs/2026-09-16/filter-loop/raw-full/r0/corpus.txt).
#
# WARN_BYTES is the other half: above it the read stops being imperceptible
# (32 MB is 35 ms warm, but a cold read off a slow disk or a network share is
# tens of times that), so a caller should say something before it blocks.
# home.py measured its old Tk-thread read of an 88 MB file at 0.67 s with
# nothing on screen to say so.
# --------------------------------------------------------------------------
MAX_BYTES = 256 * 1024 * 1024
WARN_BYTES = 32 * 1024 * 1024

#: The same probe size is_trainable_file uses, so the cheap check here and the
#: cheap check there look at the same bytes.
PROBE_BYTES = 8192

#: FROM make_corpus.py:242, which has warned above this since the corpus could
#: be anything. Every distinct character costs an embedding row and an output
#: column, and the rare ones cannot be learned from two examples. The number
#: lived in a print() that only ever reached a terminal; say_vocabulary is the
#: same judgement in the shape both windows can show.
VOCAB_WARN = 300

#: Below this many appearances a character cannot be learned — also
#: make_corpus.py:243.
RARE_BELOW = 10


# --------------------------------------------------------------------------
# THE ENCODING LADDER, in the order it is tried, and why that order.
#
# 1. A BYTE ORDER MARK DECIDES OUTRIGHT. The bytes come from the codecs module
#    (docs.python.org/3/library/codecs.html), never from a literal typed here:
#    "These constants define various byte sequences, being Unicode byte order
#    marks (BOMs) for several encodings." utf-8-sig is the codec for the UTF-8
#    signature — "On decoding, an optional UTF-8 encoded BOM at the start of
#    the data will be skipped" — which is why the mark does not survive into
#    the text.
#
#    LONGEST MARK FIRST, AND THAT IS ENFORCED BELOW RATHER THAN REMEMBERED:
#    BOM_UTF32_LE is b"\xff\xfe\x00\x00" and BOM_UTF16_LE is b"\xff\xfe", so a
#    UTF-32 file tested against UTF-16 first matches the wrong one and decodes
#    to a string full of NULs. Sorting by length is one line and cannot drift.
#
#    UTF-16 IS THE CASE THAT MATTERS MOST. It is one of the five entries in
#    Notepad's Save as list, so it is not exotic — it is what somebody gets by
#    picking the line next to the one they meant, and under errors="ignore" a
#    3,120-character file came back as 6 characters with a tick beside it.
#
# 2. STRICT UTF-8. Everything written this century, and the only decode the
#    code being replaced ever attempted.
#
# 3. ONE LEGACY RUNG: cp1252, tried strictly.
#
#    WHY NOT latin-1, WHICH IS THE OBVIOUS FALLBACK. Measured on this Python
#    over all 256 single byte values:
#        cp1252        refuses 5 of 256  (0x81, 0x8D, 0x8F, 0x90, 0x9D)
#        latin-1       refuses 0
#        iso-8859-15   refuses 0
#        mac_roman     refuses 0
#        koi8-r        refuses 0
#        cp437         refuses 0
#    Those five are the ones unicode.org/Public/MAPPINGS/VENDORS/MICSFT/WINDOWS
#    /CP1252.TXT marks "#UNDEFINED". An encoding that refuses nothing cannot
#    fail, so putting latin-1 at the end of a ladder does not add a fallback —
#    it DELETES the refusal. Every PNG, every video, every half-downloaded file
#    would decode "successfully" into 256 kinds of noise and walk into a
#    character model's permanent vocabulary. latin-1 is a way of writing bytes
#    down, not a hypothesis that can be wrong, so it is not in the ladder.
#
#    AND IT COSTS NOTHING, because cp1252 and latin-1 agree on every byte from
#    0xA0 to 0xFF — all 96 of them, checked — which is where the accented
#    letters live. A real Latin-1 file decodes here with every accent intact.
#    They differ only over 0x80-0x9F, where ISO-8859-1 has C1 control
#    characters and cp1252 has the curly quotes and dashes that Word writes;
#    text made of C1 controls is not text, and text with curly quotes is
#    extremely common, so where they disagree cp1252 is the better guess.
#
#    THE ADMISSION RULE FOR THIS LIST, so the next person has one: a codec may
#    join it only if it refuses at least one byte value, and the list is
#    ordered most-refusing first. That keeps every rung falsifiable.
#
#    WHAT THIS LADDER HONESTLY CANNOT DO: tell cp1252 from cp1251 or KOI8-R. A
#    Russian file in cp1251 decodes as cp1252 into Latin mojibake that passes
#    every structural test there is, because both encodings define nearly all
#    256 bytes. No amount of ordering fixes that; only character statistics or
#    a declaration would, and both are out of scope for a reader that must be
#    explainable. What is done instead is to REPORT the encoding that won, on
#    screen, so a person who knows their file is Russian can see "cp1252" and
#    know to re-save it as UTF-8. A guess that says which guess it made is a
#    different thing from a guess that does not.
#
# 4. NOTHING DECODED IT: refuse, naming what was tried. Never half a string.
#
# A BOM-LESS UTF-16 FILE IS REFUSED, and that is deliberate. Half its bytes are
# NUL so it cannot pass the text rule, and "try utf-16 on anything with a lot
# of NULs" is not safe: strict UTF-16 accepts almost any even-length byte
# string, so it would turn binary into plausible-looking text. A file with no
# BOM carries no declaration, and this file does not invent one.
# --------------------------------------------------------------------------
_BOMS_DECLARED = (
    (codecs.BOM_UTF32_LE, "utf-32", "utf-32 (BOM)"),
    (codecs.BOM_UTF32_BE, "utf-32", "utf-32 (BOM)"),
    (codecs.BOM_UTF8, "utf-8-sig", "utf-8-sig (BOM)"),
    (codecs.BOM_UTF16_LE, "utf-16", "utf-16 (BOM)"),
    (codecs.BOM_UTF16_BE, "utf-16", "utf-16 (BOM)"),
)
#: Longest first, by construction. See the note above about BOM_UTF32_LE.
BOMS = tuple(sorted(_BOMS_DECLARED, key=lambda row: -len(row[0])))

#: Tried strictly, in this order, after the BOM check and strict UTF-8.
LEGACY_ENCODINGS = ("cp1252",)

#: Never tried automatically: each of these decodes all 256 byte values, so it
#: can only ever turn a refusal into a false accept. Named rather than merely
#: omitted, so the next person can see the decision was made.
NEVER_GUESSED = ("latin-1", "iso-8859-1", "iso-8859-15", "mac_roman", "koi8-r",
                 "cp437")

_PDF_MAGIC = b"%PDF-"          # rfc-editor.org/rfc/rfc8118.txt sec 8: "All PDF
                               # files start with the characters \"%PDF-\""
_RTF_MAGIC = b"{\\rtf"         # biblioscape.com/rtf15_spec.htm, RTF SYNTAX
_ZIP_MAGIC = b"PK\x03\x04"

_DOCX_EXTS = {".docx"}
_EPUB_EXTS = {".epub"}
_HTML_EXTS = {".html", ".htm", ".xhtml"}
_PDF_EXTS = {".pdf"}
_RTF_EXTS = {".rtf"}
#: Everything this file can open, whatever BINARY_EXTS says about the name.
_HANDLED_EXTS = _DOCX_EXTS | _EPUB_EXTS | _HTML_EXTS

#: Public, because a caller with its own name-based refusal list has to know
#: which of those names this module can now open. make_corpus.py refuses
#: .docx and .epub from BINARY_EXTS before it ever asks can_train_on, which was
#: right while nothing here could read a zip container and became a silent
#: disagreement the moment it could: the window accepted a Word document and
#: `make_corpus.py --src` skipped the same file without saying so.
HANDLED_EXTS = frozenset(_HANDLED_EXTS)


def _bom_of(data: bytes) -> tuple[bytes, str, str] | None:
    for bom, codec, label in BOMS:
        if data.startswith(bom):
            return bom, codec, label
    return None


def decode_bytes(data: bytes, prefer: str = "") -> tuple[str | None, str, list[str]]:
    """(text, encoding, what was tried). text is None when nothing decoded it.

    `prefer` is a codec named by the file itself — an HTML meta charset — which
    is tried after the BOM and before UTF-8, and which is allowed to be wrong:
    a declaration is a hint, not a fact, and plenty of pages carry one that
    does not match what was saved.

    Every decode is strict. codecs' own description of the alternative is the
    whole argument: 'ignore' means "Ignore the malformed data and continue
    without further notice" (docs.python.org/3/library/codecs.html), and
    "without further notice" is precisely what this program cannot afford.
    """
    tried: list[str] = []
    found = _bom_of(data)
    if found is not None:
        _, codec, label = found
        tried.append(label)
        try:
            return data.decode(codec), label, tried
        except UnicodeDecodeError:
            # The file declared itself and then did not match. Falling through
            # to another encoding here would mean ignoring a declaration in
            # favour of a guess, which is how a truncated UTF-16 file becomes
            # a page of mojibake instead of a sentence about a damaged file.
            return None, "", tried
    if prefer:
        tried.append(prefer)
        try:
            return data.decode(prefer), prefer, tried
        except (UnicodeDecodeError, LookupError):
            pass
    for codec in ("utf-8", *LEGACY_ENCODINGS):
        tried.append(codec)
        try:
            return data.decode(codec), codec, tried
        except UnicodeDecodeError:
            continue
    return None, "", tried


def _undecodable_count(data: bytes) -> int:
    """How many bytes UTF-8 could not make a character of.

    THE REPLACEMENT STRING IS COUNTED AND THROWN AWAY. It never leaves this
    function and is never anybody's text, which is the whole difference between
    counting a loss and shipping one: `dropped` exists so a refusal can say
    "12,431 bytes of that file are not characters" instead of "no".
    """
    return data.decode("utf-8", "replace").count("�")


# --------------------------------------------------------------------------
# JUDGEMENTS. Every one of them is a look.Say, so a window renders a refusal
# and an accept through the same three lines and neither can arrive as a raw
# string nobody styled.
# --------------------------------------------------------------------------
def _refused(word: str, why: str, dropped: int = 0) -> Read:
    return Read(None, "refused", "", dropped,
                look.Say(look.REFUTED, word, why, "refuted"))


def _accepted(text: str, kind: str, encoding: str, say: look.Say) -> Read:
    return Read(text, kind, encoding, 0, say)


_KIND_WORDS = {
    "text": "",
    "docx": " (a Word document)",
    "epub": " (an EPUB book)",
    "html": " (a saved web page)",
}


def _read_say(name: str, text: str, kind: str, encoding: str) -> look.Say:
    """One sentence about a file that was read properly.

    It names the count because that is the fact a person can check against what
    they expected, and the encoding only when it was not plain UTF-8 — saying
    "read as utf-8" every time is noise, and saying it about the one file in
    fifty that was cp1252 is how somebody spots a wrong guess.
    """
    why = f"Read {len(text):,} characters out of “{name}”{_KIND_WORDS.get(kind, '')}."
    if encoding and encoding != "utf-8":
        why += (f" It is not plain UTF-8 — it decoded as {encoding}, and nothing "
                f"was dropped.")
    return look.Say(look.PROVED, "Read", why, "proved")


def say_vocabulary(text: str) -> look.Say:
    """How big an alphabet this text buys, and what that costs.

    MOVED OUT OF A print(). make_corpus.py:242 has warned above VOCAB_WARN
    distinct characters since the corpus could be anything, and that warning
    only ever reached a terminal — so the person using the window, who is
    exactly the person who does not open a terminal, never saw it.

    The threshold and both facts in the sentence are make_corpus's, unchanged.
    What is different is the counting: make_corpus.py:243 spends
    `body.count(c)` per distinct character, which is a full pass over the
    corpus for each one. On the 67 MB corpus measured at the top of this file,
    with the 5,183 distinct characters a Chinese corpus really has, that is
    5,183 passes over 48.7 million characters. Counter does it in one.
    """
    vocab = set(text)
    n = len(vocab)
    if n <= VOCAB_WARN:
        return look.Say(
            look.PROVED, "Alphabet fits",
            f"{n:,} different characters, which is an ordinary alphabet for a "
            f"character model to learn.", "proved")
    counts = Counter(text)
    rare = sum(1 for c in vocab if counts[c] < RARE_BELOW)
    return look.Say(
        look.NOT_APPLICABLE, "Big alphabet",
        f"{n:,} different characters is a large alphabet, and {rare:,} of them "
        f"appear fewer than {RARE_BELOW} times in the whole text. Each one costs "
        f"a row of the model whether it is learned or not, and the rare ones "
        f"cannot be learned from that few examples — narrowing the input to one "
        f"kind of file, or dropping the ones with unusual symbols, buys the "
        f"model back.", "unsettled")


def size_of(path) -> int:
    """Bytes on disk, or -1 when there is nothing there. Costs one stat()."""
    try:
        return Path(path).stat().st_size
    except OSError:
        return -1


def _size_words(n: int) -> str:
    """A size in the unit a person would say it in.

    "0 MB" is what a fixed unit does to a small file, and a sentence that says
    a 400-byte file is 0 MB reads as a bug even when the refusal is right.
    """
    if n < 1000:
        return f"{n:,} bytes"
    if n < 1000 * 1000:
        return f"{n / 1e3:,.0f} kB"
    return f"{n / 1e6:,.1f} MB" if n < 10 * 1000 * 1000 else f"{n / 1e6:,.0f} MB"


def check_size(path, max_bytes: int = MAX_BYTES) -> look.Say:
    """What to say about a file's size WITHOUT opening it — 1.3 microseconds.

    For a window that is about to block on a read: this is the answer it can
    have before it decides to, which is the difference between warning somebody
    and freezing on them.
    """
    n = size_of(path)
    name = Path(path).name
    if n < 0:
        return look.Say(look.REFUTED, "Not there",
                        f"There is nothing at “{name}” to read.", "refuted")
    if n == 0:
        return look.Say(look.REFUTED, "Empty",
                        f"“{name}” is empty — there is nothing in it to learn "
                        f"from.", "refuted")
    if n > max_bytes:
        return look.Say(
            look.REFUTED, "Too big",
            f"“{name}” is {_size_words(n)}, over the {_size_words(max_bytes)} "
            f"this will read in one go — reading it needs about twice its size "
            f"in memory. Split it, or point this at part of it.", "refuted")
    if n > WARN_BYTES:
        return look.Say(
            look.NOT_APPLICABLE, "Large",
            f"“{name}” is {_size_words(n)}, so reading it will take a moment and "
            f"the window will say when it is done.", "unsettled")
    return look.Say(look.PROVED, "Fits",
                    f"“{name}” is {_size_words(n)}, which reads instantly.",
                    "proved")


# --------------------------------------------------------------------------
# HTML. html.parser, and the two elements whose contents are not words.
#
# The standard library says this in so many words: handle_data "is called to
# process arbitrary data (e.g. text nodes and the content of elements like
# script and style)" (docs.python.org/3/library/html.parser.html). So the
# JavaScript and the CSS of a saved page arrive at exactly the same door as the
# prose, and a reader that does not track those two tags puts a page's minified
# jQuery into the training corpus.
# --------------------------------------------------------------------------
_DROP_CONTENT = {"script", "style"}

#: Tags that end a line of prose. Without them "</p><p>" welds the last word of
#: one paragraph to the first word of the next, inventing a word that is in
#: nobody's text.
_BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3",
    "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre",
    "section", "table", "td", "th", "title", "tr", "ul",
}


class _TextOnly(HTMLParser):
    """Text nodes, with script and style left behind."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._drop = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _DROP_CONTENT:
            self._drop += 1
        elif tag in _BLOCK_TAGS:
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROP_CONTENT:
            # Never below zero: html.parser is documented not to "check that end
            # tags match start tags", so a stray </script> in a badly written
            # page must not leave the counter negative and silently un-drop the
            # next real script.
            self._drop = max(0, self._drop - 1)
        elif tag in _BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._drop:
            self.out.append(data)

    def text(self) -> str:
        return _tidy("".join(self.out))


def _tidy(text: str, keep_tabs: bool = False) -> str:
    """Collapse the whitespace that markup leaves behind.

    Runs of spaces become one space and runs of blank lines become one blank
    line, because indentation in the source of a page is not a feature of the
    prose — but the line structure is kept, since paragraph breaks are
    something a character model can learn.

    `keep_tabs` is for the formats where a tab is CONTENT rather than layout. A
    Word document's w:tab is a character the author typed; a tab at the start
    of a line of HTML source is the person who wrote the page indenting it.
    Collapsing both looked tidier and silently welded the columns of every
    tabbed list in every .docx into one run of words.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \f\v]+" if keep_tabs else r"[ \t\f\v]+", " ", text)
    text = re.sub(r"[ \f\v]*\n[ \f\v]*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


#: The encoding declaration a page carries about itself. The HTML Standard
#: limits authors to the first 1024 bytes and says user agents are "encouraged
#: to use the prescan algorithm below ... on the first 1024 bytes, but not to
#: stall beyond that" (html.spec.whatwg.org/multipage/parsing.html, 13.2.3.2),
#: so that is the window searched here. This is a much smaller thing than the
#: standard's prescan — it does not tokenise — and it is allowed to be wrong,
#: because whatever it names is still tried strictly and still has to decode.
_META_CHARSET = re.compile(
    rb"""<meta[^>]*?charset\s*=\s*["']?\s*([A-Za-z0-9_.:+-]+)""", re.I)


def _declared_encoding(head: bytes) -> str:
    m = _META_CHARSET.search(head[:1024])
    if not m:
        return ""
    try:
        # Strict, like every other decode here, although the pattern above can
        # only match ASCII: the rule is worth more than the one byte it saves.
        return codecs.lookup(m.group(1).decode("ascii")).name
    except (LookupError, UnicodeDecodeError):
        return ""


def _html_text(data: bytes) -> tuple[str | None, str, list[str]]:
    """(text, encoding, tried) for a page's bytes."""
    text, encoding, tried = decode_bytes(data, prefer=_declared_encoding(data))
    if text is None:
        return None, "", tried
    parser = _TextOnly()
    parser.feed(text)
    parser.close()
    return parser.text(), encoding, tried


# --------------------------------------------------------------------------
# ZIP CONTAINERS: .docx and .epub are both XML in a zip.
#
# A BUDGET, NOT A TRUST. docs.python.org/3/library/xml.html's XML security
# section names the decompression bomb — a few kB that expands to gigabytes —
# so every member is read through a ceiling rather than by asking the zip's own
# central directory how big it claims to be, since that number is written by
# whoever made the file. What this does NOT protect against is entity expansion
# inside the XML itself: the same page says Expat below 2.7.2 "may be
# vulnerable to the 'billion laughs' ... vulnerabilities", and there is no
# standard-library switch to turn entity expansion off. Saying so is the honest
# option; claiming this is hardened against a hostile .docx would not be.
# --------------------------------------------------------------------------
def _zip_read(zf: zipfile.ZipFile, name: str, ceiling: int) -> bytes | None:
    try:
        with zf.open(name) as f:
            data = f.read(ceiling + 1)
    except (KeyError, OSError, zipfile.BadZipFile, RuntimeError):
        return None
    return None if len(data) > ceiling else data


def _xml(data: bytes) -> ET.Element | None:
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        return None


def _local(tag: str) -> str:
    """The element name without its namespace, for the lenient reads.

    Used where a real file in the wild may be missing the namespace the
    specification requires — a container.xml written by hand, say. Where the
    namespace is what distinguishes one element from another it is matched in
    full instead.
    """
    return tag.rsplit("}", 1)[-1]


# WordprocessingML, from python-docx's own namespace map (github.com/
# python-openxml/python-docx, src/docx/oxml/ns.py, read 2026-09-21). python-docx
# is the reference implementation, and it is READ rather than depended on: it
# pulls lxml, and the dependency claim here is PyTorch and Tk.
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_PKG_RELS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_RT_OFFICE_DOCUMENT = ("http://schemas.openxmlformats.org/officeDocument/2006/"
                       "relationships/officeDocument")


def _docx_main_part(zf: zipfile.ZipFile, ceiling: int) -> str:
    """Which member holds the document, asked rather than assumed.

    "word/document.xml" is the conventional name and the fallback here, but the
    part that counts is the one the package relationships point at with the
    officeDocument relationship type, which is how python-docx finds it
    (src/docx/opc/constants.py, RT.OFFICE_DOCUMENT). A .docx written by
    something other than Word may name the part differently and still be
    perfectly valid.
    """
    data = _zip_read(zf, "_rels/.rels", ceiling)
    root = _xml(data) if data else None
    if root is not None:
        for rel in root.iter(_PKG_RELS + "Relationship"):
            if rel.get("Type") == _RT_OFFICE_DOCUMENT:
                target = (rel.get("Target") or "").lstrip("/")
                if target:
                    return target
    return "word/document.xml"


def _docx_text(root: ET.Element) -> str:
    """The characters of a Word document, in document order.

    THE ELEMENT LIST IS NOT GUESSED. python-docx's CT_R.text joins exactly
    `w:br | w:cr | w:noBreakHyphen | w:ptab | w:t | w:tab` (src/docx/oxml/text/
    run.py), so those are the six handled here — a reader that takes only w:t
    welds the two halves of a hyphenated word together and turns every tab and
    line break into nothing.

    A w:p ends a line. A table's cells therefore arrive as separate lines,
    which is a real limitation and a deliberate one: the alternative is
    inventing a column separator, and every character invented here is a
    character in the model's vocabulary that was in nobody's document.

    ITERATIVE, NOT RECURSIVE, because the nesting depth of the document comes
    from the file rather than from us: a table inside a table inside a text box
    is ordinary, and a file built to nest ten thousand deep would otherwise hit
    Python's recursion limit as a crash instead of a sentence.
    """
    out: list[str] = []
    stack = [(root, iter(root))]
    while stack:
        _, kids = stack[-1]
        for child in kids:
            tag = child.tag
            if tag == _W + "t":
                out.append(child.text or "")
            elif tag in (_W + "tab", _W + "ptab"):
                out.append("\t")
            elif tag in (_W + "br", _W + "cr"):
                out.append("\n")
            elif tag == _W + "noBreakHyphen":
                out.append("\u2011")   # non-breaking hyphen, written as an
                                       # escape because it is invisibly
                                       # different from "-" in source
            else:
                stack.append((child, iter(child)))
                break
        else:
            done, _ = stack.pop()
            if done.tag == _W + "p":
                out.append("\n")
    return _tidy("".join(out), keep_tabs=True)


# EPUB, from the W3C Recommendation (w3.org/TR/epub-33, 13 January 2026):
# container.xml lives at META-INF/container.xml and its elements are in the
# urn:oasis:names:tc:opendocument:xmlns:container namespace; rootfile carries
# `full-path`, "the relative file path to the package document". Section 5:
# "All XML elements defined in this section are in the
# http://www.idpf.org/2007/opf namespace", where manifest item carries id, href
# and media-type and spine itemref carries idref, "identifies an item in the
# manifest".
_OCF = "{urn:oasis:names:tc:opendocument:xmlns:container}"
_OPF = "{http://www.idpf.org/2007/opf}"
_XHTML_TYPE = "application/xhtml+xml"


def _epub_parts(zf: zipfile.ZipFile, ceiling: int) -> list[str]:
    """The reading order: the spine, resolved through the manifest.

    THE SPINE AND NOT THE ZIP LISTING. A zip's order is whatever the writer
    happened to use, and an EPUB routinely carries chapters the spine does not
    include — a cover page, an unused stylesheet's fallback, leftovers from an
    earlier edition. Reading the spine is reading the book; reading the listing
    is reading the box it came in.
    """
    data = _zip_read(zf, "META-INF/container.xml", ceiling)
    root = _xml(data) if data else None
    if root is None:
        return []
    opf = ""
    for rootfile in root.iter():
        if _local(rootfile.tag) == "rootfile" and rootfile.get("full-path"):
            opf = unquote(rootfile.get("full-path", ""))
            break
    if not opf:
        return []
    data = _zip_read(zf, opf, ceiling)
    package = _xml(data) if data else None
    if package is None:
        return []
    base = posixpath.dirname(opf)
    manifest: dict[str, tuple[str, str]] = {}
    for item in package.iter(_OPF + "item"):
        ident, href = item.get("id"), item.get("href")
        if ident and href:
            manifest[ident] = (unquote(href), item.get("media-type", ""))
    if not manifest:
        # A file in the wild that left the namespace off. The specification
        # requires it, so the namespaced read is tried first and this is a
        # fallback rather than the rule — but refusing a book over a missing
        # xmlns helps nobody, and the elements are named the same either way.
        for item in package.iter():
            if _local(item.tag) != "item":
                continue
            ident, href = item.get("id"), item.get("href")
            if ident and href:
                manifest[ident] = (unquote(href), item.get("media-type", ""))
    refs = list(package.iter(_OPF + "itemref"))
    if not refs:
        refs = [el for el in package.iter() if _local(el.tag) == "itemref"]
    order: list[str] = []
    for ref in refs:
        got = manifest.get(ref.get("idref") or "")
        if got is None:
            continue
        href, media = got
        if media and media != _XHTML_TYPE:
            continue            # images and audio are in the spine too
        if not media and posixpath.splitext(href)[1].lower() not in (
                ".xhtml", ".html", ".htm"):
            continue
        order.append(posixpath.normpath(posixpath.join(base, href)))
    return order


# --------------------------------------------------------------------------
# THE PUBLIC THREE.
# --------------------------------------------------------------------------
def _refuse_pdf(name: str) -> Read:
    return _refused(
        "Not text",
        f"“{name}” is a PDF. A PDF stores instructions for printing glyphs "
        f"rather than characters, so reading one needs a library this project "
        f"deliberately does not carry. Open it, select everything, and save it "
        f"as a plain .txt file — or save it as .docx — and this will read that.")


def _refuse_rtf(name: str) -> Read:
    # DECIDED: REFUSE .rtf RATHER THAN STRIP IT. An RTF file is 7-bit ASCII, so
    # before this it sailed through the text rule and its control words landed
    # in the corpus as though they were prose. Stripping them properly is not a
    # regular expression: the specification (biblioscape.com/rtf15_spec.htm)
    # needs a reader that tracks brace groups, skips an unrecognised
    # "{\*\destination ...}" whole, and handles \bin, which carries raw binary
    # INSIDE the file. A half-built stripper therefore fails in the one
    # direction that costs most here — control words or binary bytes becoming
    # permanent entries in a character model's vocabulary. A refusal a person
    # can act on in ten seconds beats a parser that is wrong in a way nobody
    # sees until the model starts writing \par.
    return _refused(
        "Not text",
        f"“{name}” is Rich Text Format, which stores its formatting commands in "
        f"among the words, and this reads text rather than commands. Open it and "
        f"save it as a plain .txt file or as a .docx, and this will read that.")


def read_any(path, max_bytes: int = MAX_BYTES) -> Read:
    """Read one file of somebody's own, properly or not at all.

    The only way anything in locallm reads a file a person chose. Everything it
    can return is in Read: the characters, where they came from, what decoded
    them, and one sentence about it either way.
    """
    p = Path(path)
    name = p.name or str(p)
    try:
        if p.is_dir():
            return _refused(
                "A folder",
                f"“{name}” is a folder rather than a file. Reading a whole "
                f"folder is what read_corpus is for, and step 1 will do it if "
                f"you drop the folder on it.")
        if not p.is_file():
            return _refused("Not there",
                            f"There is nothing at “{p}” to read.")
    except OSError as e:
        return _refused("Unreadable",
                        f"“{name}” could not be opened: {e.__class__.__name__}.")

    size = size_of(p)
    if size == 0:
        return _refused("Empty", f"“{name}” is empty, so there is nothing in it "
                                 f"to learn from.")
    if size > max_bytes:
        return _refused("Too big", check_size(p, max_bytes).why)

    suffix = p.suffix.lower()
    if suffix in _PDF_EXTS:
        return _refuse_pdf(name)
    if suffix in _RTF_EXTS:
        return _refuse_rtf(name)
    if suffix in BINARY_EXTS and suffix not in _HANDLED_EXTS:
        # make_corpus's list, and its reason: refuse on the name so a 4 GB video
        # is never read off disk to be told it is a 4 GB video.
        return _refused(
            "Not text",
            f"“{name}” is a {suffix} file, which holds a picture, sound, an "
            f"archive or a program rather than characters. If it really is text, "
            f"save a copy of it as .txt.")

    try:
        with p.open("rb") as f:
            # One byte past the ceiling, so a file that grew between the stat
            # above and this read is caught here instead of being half read.
            data = f.read(max_bytes + 1)
    except OSError as e:
        return _refused("Unreadable",
                        f"“{name}” could not be read: {e.__class__.__name__}.")
    if len(data) > max_bytes:
        return _refused("Too big", check_size(p, max_bytes).why)

    # MAGIC BEFORE NAME, because the name is a claim by whoever saved it. A PDF
    # saved as notes.txt is still a PDF, and it used to arrive as 1,266
    # characters of printer instructions with a tick beside it.
    if data.startswith(_PDF_MAGIC):
        return _refuse_pdf(name)
    if data.startswith(_RTF_MAGIC):
        return _refuse_rtf(name)

    if suffix in _DOCX_EXTS or suffix in _EPUB_EXTS:
        if not data.startswith(_ZIP_MAGIC):
            return _refused(
                "Damaged",
                f"“{name}” is named like a {suffix} file but it is not one "
                f"inside — a {suffix} is a zip archive and this does not start "
                f"like one. It may have been renamed, or only half downloaded.")
        return _read_container(name, data, "docx" if suffix in _DOCX_EXTS
                               else "epub", max_bytes)

    if suffix in _HTML_EXTS:
        text, encoding, tried = _html_text(data)
        if text is None:
            return _refused_decode(name, data, tried)
        if not text.strip():
            return _refused(
                "No words",
                f"“{name}” was read, but there is no text in it once the markup "
                f"and the scripts are taken out. A page that draws itself with "
                f"JavaScript has nothing in the file to read.")
        return _accepted(text, "html", encoding,
                         _read_say(name, text, "html", encoding))

    text, encoding, tried = decode_bytes(data)
    if text is None:
        return _refused_decode(name, data, tried)
    if not text:
        # A FILE THAT IS NOTHING BUT A BYTE ORDER MARK, which is what a Save as
        # box writes for an empty document: three bytes for UTF-8, two for
        # UTF-16. The size check above cannot catch it, because there ARE bytes,
        # and falling through to the text rule below refused it as "mostly
        # characters that cannot be printed, which is what a compressed file
        # looks like" — said about a file with no characters in it at all.
        # Measured 2026-09-21 on a 3-byte codecs.BOM_UTF8 file.
        #
        # Nothing else can reach here: an empty decode with no mark means empty
        # bytes, and size == 0 is already refused above.
        return _refused(
            "Empty",
            f"“{name}” holds only the few bytes that say which encoding it is "
            f"in, and no writing after them, so there is nothing in it to learn "
            f"from.")
    if not text_is_readable(text):
        # make_corpus's rule, applied to the WHOLE file rather than a probe.
        return _refused(
            "Not text",
            f"“{name}” decoded as {encoding}, but what came out is not writing — "
            f"it is mostly characters that cannot be printed, which is what a "
            f"program, a database or a compressed file looks like when it is "
            f"read as text.")
    return _accepted(text, "text", encoding,
                     _read_say(name, text, "text", encoding))


def _refused_decode(name: str, data: bytes, tried: list[str]) -> Read:
    """Nothing decoded it: say what was tried, and how much of it is not text."""
    declared = _bom_of(data)
    if declared is not None:
        return _refused_declaration(name, data, declared[1], tried[0])
    lost = _undecodable_count(data)
    return _refused(
        "Not text",
        f"“{name}” is not text in any encoding this knows. It was tried as "
        f"{', '.join(tried)}, and {lost:,} of its bytes are not characters in "
        f"any of them. Nothing was read rather than read partly — if this really "
        f"is writing, open it in the program that made it and save it as UTF-8.",
        dropped=lost)


def _refused_declaration(name: str, data: bytes, codec: str, label: str) -> Read:
    """The file named its own encoding in a byte order mark and then broke it.

    A SENTENCE OF ITS OWN BECAUSE THE GENERIC ONE CARRIED A NUMBER FROM THE
    WRONG CODEC. When a mark fails, decode_bytes returns without trying anything
    else — a declaration is not overruled by a guess — so `tried` holds one
    entry and _undecodable_count's figure is measured against UTF-8, which never
    ran. MEASURED 2026-09-21 on the UTF-16 fixture truncated by one byte, 5,041
    bytes: the old sentence read "it is not text in any encoding this knows ...
    2 of its bytes are not characters in any of them", the two being the mark
    itself, since every other byte of an English UTF-16 file is ASCII or NUL and
    UTF-8 decodes both. The file was UTF-16; it was one byte short.
    unicode.org/faq/utf_bom.html puts the mark's job plainly — for UTF-16 and
    UTF-32 "the byte order is determined by a byte order mark, if present at the
    beginning of the data stream" — so the mark is a declaration ABOUT the rest
    of the file, and a declaration that does not hold means damage rather than
    an unknown encoding.

    The decode is repeated to find out where it stops, which costs one strict
    pass over a file that is being refused anyway, and gives `dropped` a figure
    measured against the codec the file itself named.
    """
    lost, where = 0, ""
    try:
        data.decode(codec)
    except UnicodeDecodeError as e:
        lost = len(data) - e.start
        where = (f" It decodes as far as byte {e.start:,} of {len(data):,} and "
                 f"stops there.")
    return _refused(
        "Damaged",
        f"“{name}” starts by declaring itself {label} and then does not decode "
        f"as it.{where} That is what a file cut short by a failed download or a "
        f"full disk looks like. Nothing was read rather than read partly — save "
        f"it again from whatever made it.", dropped=lost)


def _read_container(name: str, data: bytes, kind: str, max_bytes: int) -> Read:
    """.docx and .epub: XML in a zip, extracted with the standard library."""
    try:
        zf = zipfile.ZipFile(BytesIO(data))
    except (zipfile.BadZipFile, OSError):
        return _refused(
            "Damaged",
            f"“{name}” could not be opened as a {kind} file. The archive inside "
            f"it is damaged, so nothing was taken out of it.")
    with zf:
        if kind == "docx":
            part = _docx_main_part(zf, max_bytes)
            raw = _zip_read(zf, part, max_bytes)
            root = _xml(raw) if raw else None
            if root is None:
                return _refused(
                    "Damaged",
                    f"“{name}” is a Word document whose text part ({part}) is "
                    f"missing or unreadable, so nothing was taken out of it.")
            text = _docx_text(root)
        else:
            parts = _epub_parts(zf, max_bytes)
            if not parts:
                return _refused(
                    "Damaged",
                    f"“{name}” is an EPUB with no readable reading order in it, "
                    f"so there is nothing to take the chapters from.")
            chapters: list[str] = []
            for member in parts:
                raw = _zip_read(zf, member, max_bytes)
                if raw is None:
                    continue
                one, _, _ = _html_text(raw)
                if one:
                    chapters.append(one)
            text = _tidy("\n\n".join(chapters))
    if not text.strip():
        return _refused(
            "No words",
            f"“{name}” opened, but there are no words in it — it may hold only "
            f"pictures, or only the parts that say how it should look.")
    return _accepted(text, kind, "utf-8", _read_say(name, text, kind, "utf-8"))


def can_train_on(path) -> bool:
    """Cheap yes/no for a picker or a drop target. It decides nothing.

    read_any decides, and read_any is the only thing allowed to say WHY — this
    exists so that choosing a 4 GB video does not read a 4 GB video, and it
    reads at most PROBE_BYTES to answer.

    IT CANNOT BE is_trainable_file ALONE, which is the trap here. That function
    decodes its probe as UTF-8 and refuses anything holding a NUL byte, which
    is right for make_corpus and wrong for a picker: every UTF-16 file has NUL
    bytes in it by design, so a picker built on it would grey out exactly the
    file this whole round exists to accept. What is reused instead is the rule
    underneath — trim_to_char_boundary and text_is_readable — with the ladder
    deciding which bytes are characters.
    """
    p = Path(path)
    try:
        if not p.is_file():
            return False
    except OSError:
        return False
    if any(seg in SKIP_DIRS for seg in p.parts):
        return False
    suffix = p.suffix.lower()
    if suffix in _PDF_EXTS or suffix in _RTF_EXTS:
        return False
    try:
        with p.open("rb") as f:
            head = f.read(PROBE_BYTES)
    except OSError:
        return False
    if not head:
        return False
    if head.startswith(_PDF_MAGIC) or head.startswith(_RTF_MAGIC):
        return False
    if suffix in _DOCX_EXTS or suffix in _EPUB_EXTS:
        return head.startswith(_ZIP_MAGIC)
    if suffix in BINARY_EXTS:
        return False
    if _bom_of(head) is not None:
        # A byte order mark is a declaration, and this is the cheap check: it
        # says yes and lets read_any do the real decode, which is also the only
        # place that can explain a declaration that turned out to be a lie.
        return True
    text, _, _ = decode_bytes(trim_to_char_boundary(head))
    return text is not None and text_is_readable(text)


def read_corpus(paths, max_bytes: int = MAX_BYTES) -> Read:
    """Several files, or a folder, read and joined into one corpus.

    JOINED WITH A BLANK LINE AND NOTHING ELSE. make_corpus writes a
    "# file: name" header before each document, which is right for a file a
    person will open and read; it is wrong here, because in a character model
    every character invented by the reader is a character the model learns to
    write. A blank line between documents is punctuation every corpus already
    has.

    A file that is not text is SKIPPED AND COUNTED, not fatal: a folder of
    letters with one photograph in it is a folder of letters. Only a folder
    where nothing at all could be read comes back refused.
    """
    if isinstance(paths, (str, Path)):
        paths = [paths]
    files: list[Path] = []
    roots = [Path(one) for one in paths]
    if not roots:
        return _refused("Nothing chosen",
                        "No file or folder was given to read.")
    for root in roots:
        if root.is_dir():
            files.extend(sorted(q for q in root.rglob("*") if q.is_file()))
        else:
            files.append(root)
    where = roots[0].name if len(roots) == 1 else f"{len(roots)} places"

    if not files:
        return _refused("Nothing there",
                        f"There are no files in “{where}” to read.")

    total = sum(max(size_of(f), 0) for f in files)
    if total > max_bytes:
        return _refused(
            "Too big",
            f"“{where}” holds {_size_words(total)} across {len(files):,} files, "
            f"over the {_size_words(max_bytes)} this reads in one go. Point it "
            f"at part of it, or join the files you want yourself.")

    parts: list[str] = []
    kinds: set[str] = set()
    encodings: set[str] = set()
    skipped = 0
    reasons: Counter = Counter()
    for f in files:
        if not can_train_on(f):
            skipped += 1
            continue
        got = read_any(f, max_bytes)
        if got.text is None:
            skipped += 1
            reasons[got.say.word] += 1
            continue
        parts.append(got.text)
        kinds.add(got.kind)
        encodings.add(got.encoding)

    if not parts:
        detail = ", ".join(f"{n} {word.lower()}" for word, n in reasons.most_common())
        return _refused(
            "Nothing readable",
            f"None of the {len(files):,} files in “{where}” could be read as "
            f"text" + (f" ({detail})." if detail else ".") +
            " Text files of any kind work, and so do .docx, .epub and saved web "
            "pages.")

    text = "\n\n".join(parts)
    # One kind or one encoding when they agree, which is the common case and the
    # useful answer; the honest word when they do not. Neither field may be a
    # guess about the majority — "mostly cp1252" is not a fact about any
    # particular character in here.
    kind = kinds.pop() if len(kinds) == 1 else "text"
    # "mixed encodings" rather than "mixed" because home.py renders this field
    # into a sentence — "Read as {encoding}, not plain UTF-8" — and a word that
    # only makes sense as a label reads as a bug there.
    encoding = encodings.pop() if len(encodings) == 1 else "mixed encodings"
    why = (f"Read {len(parts):,} file{'' if len(parts) == 1 else 's'} out of "
           f"“{where}” — {len(text):,} characters.")
    if skipped:
        why += (f" {skipped:,} other file{'' if skipped == 1 else 's'} in there "
                f"{'is' if skipped == 1 else 'are'} not text and "
                f"{'was' if skipped == 1 else 'were'} left out.")
    return Read(text, kind, encoding, 0,
                look.Say(look.PROVED, "Read", why, "proved"))
