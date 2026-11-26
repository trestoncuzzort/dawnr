"""dawnr_agent/quotes.py: the quotes in an answer that are in nothing the session read (2026-11-26).

An answer can quote a file from memory instead of from what was read, and still set the quote in a code block or
a blockquote, where it looks like the file's own text: a condition with a clause gone, two lines run into one, an
error message in other words. The case this was written for is in test_dawnr_quotes.py: a patch tests
`hit.mFraction` and `HasContactInCurrentStep` over two lines, and the answer's code block had an `if` on
`HasContactInCurrentStep` alone. This takes the quoted material in a final answer (Markdown) and looks for each
piece in the texts the session read (its tool results: fs_read windows, fs_search hits, patches); what is in none
of them is returned, for the person to be told.

Quoted material is every line of a fenced code block (``` or ~~~, with a language or without), every blockquote
line without its ">", and every passage of six words or more in double quotes, straight or curly (U+201C, U+201D),
on a line of prose. A line of a code block whose language is diff, patch or udiff is compared as what it quotes:
without its "-", "+" or " ", a hunk header by its heading, a line that names the files not at all; it is reported
as the answer has it. Whitespace does not count on either side: each run of it is one space, and there is none at
the ends. A quote is found when it is inside one line of a source, the line as it was read. A blockquote line or a
passage in quotes can run across the source's line breaks, so it is also found when it is inside the source's
whole text, its lines joined by spaces, each line first taken without fs_read's line number and tab and then
without a patch's one-character "+", "-" or " ": a quote of a patch's lines without their markers is found, and a
patch is joined once more as each of its two texts, without its "-" lines and without its "+" lines. The lines of
one file are joined the same way wherever the tools showed them, in two fs_read windows, as two fs_search hits or
as one of each: each line without what the tool put on or around it (a hit's file name and number, a window's
header and hints, a document's page marks), and only lines the file has one after the other, in one version of it
(two windows whose sha256 differ, read on either side of an edit, are not joined). A blockquote line or
a passage is also found without Markdown's inline formatting on either side (a backslash before punctuation, a code
span's backticks, emphasis), which a reader does not see; a code line keeps every character. Never reported: a
quote with nothing in it to check (no letter or digit, as in punctuation, brackets or an ellipsis, or fewer than
four characters that are not spaces), a fence inside a blockquote, a passage of fewer than six words.

This is the test locallm/rag_quote.py makes of a quote (word for word in a document, whitespace folded), made of
free Markdown instead of a quoting syntax. Found means copied, not right: a line copied exactly from the old side
of a patch is found as surely as one from the new. Text in, text out (None for a text is no text: no quotes,
nothing read); standard library only.
"""
from __future__ import annotations

import re
from typing import Iterable, NamedTuple

FENCE = re.compile(r"\s*(`{3,}|~{3,})(.*)")          # a code fence, and the rest of its line
MARKERS = re.compile(r"\s*(?:>\s?)+")                # a blockquote line's ">", nested ones too
NUMBER = re.compile(r" *(\d{1,15})\t")                   # fs_read's line number, right-aligned, and its tab
QUOTED = re.compile(r'"([^"]*)"|\u201c([^\u201c\u201d]*)\u201d')
WORDS = 6                                           # a passage in quotes of fewer words is a phrase
# Compared, not shown (2026-11-26: five of the six quotes a 27B's three reviews had reported were copied, and differed
# from what was read only in these): a comment's marker at the start of a line, where a comment runs on; a Markdown
# link, which a reader quotes by its text; quote marks of every style and escaped ones, as one.
COMMENT = re.compile(r"\s*(?:/\*+|\*+/?|//+|#+|--|;+)\s?")
# what was read is untrusted text, up to 64,000 characters a reply: a link's text holds no bracket and its address
# no parenthesis, so each character is looked at from one place only (a file of brackets took 4 seconds a read when
# either could run on to the next one; 2026-11-26)
LINK = re.compile(r"\[([^\[\]\n]*)\]\([^()\n]*\)")
QUOTE_MARKS = str.maketrans(dict.fromkeys("'\u2018\u2019\u201a\u201b\u2032\u201c\u201d\u201e\u201f\u2033", '"'))
# What the tools show of a file's lines, and around them (dawnr_agent/files.py): an fs_read window's header (the file,
# its first and last line, and the file's sha256 when it was read whole), the same for a document's text, whose
# pages are marked on lines of their own; a search's header, then each hit after its file's name and its number; and
# a reply cut at its size. Lines a file has one after the other are one text however the tools showed them: in two
# windows of one version of it, as two hits, a window and a hit.
WINDOW = re.compile(r"(.*): lines (\d{1,15})-(\d{1,15}) of \d+, \d+ bytes(?:, sha256 ([0-9a-f]+))?")
# the reader's name for what it read ("pdf, 2 pages", "text (cp1252)": doc_read.read) holds brackets one deep at most
DOCUMENT = re.compile(r"(.*) \(((?:[^()]|\([^()]*\))*)\): lines (\d{1,15})-(\d{1,15}) of \d+ of its text, \d+ bytes$")
PAGE = re.compile(r"\[page \d+\]$")
SEARCH = re.compile(r"search for .* \(literal, .*\): \d+ matches in \d+ files, \d+ files searched$")
HIT = re.compile(r"(.+?):(\d{1,15}): (.*)")
CLIPPED = re.compile(r"\[truncated at \d+ characters\]$")
# A unified diff (POSIX diff, "Diff -u or -U Output Format",
# pubs.opengroup.org/onlinepubs/9799919799/utilities/diff.html; git-scm.com/docs/git-diff, "Generating patch text
# with -p") is two texts, the old one's lines marked "-", the new one's "+", the lines of both " ", and its own
# syntax: each hunk's header with the lines it covers, "@@ -12,2 +12,2 @@", which git follows with the name of the
# function the hunk is in; and the lines that name the files ("---", "+++", and git's "diff --git" and extended
# headers). In what was read, a patch is a text with a hunk header, or a file named .patch or .diff; in an answer, a
# code block whose language is diff, patch or udiff.
HUNK = re.compile(r"@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
HUNK_HEAD = re.compile(r"@@ .*?@@ ?")                # an answer's, whose numbers may be anything
DIFF_FILES = re.compile(r"diff --git |index [0-9a-f]+\.\.[0-9a-f]+|(?:---|\+\+\+) \S+(?:$|\t)|(?:old|new) mode "
                        r"|(?:new|deleted) file mode |(?:dis)?similarity index |rename (?:from|to) |copy (?:from|to) "
                        r"|Binary files |\\ No newline at end of file")
DIFF_TAGS = ("diff", "patch", "udiff")
# Markdown's inline formatting, which a reader of the text does not see (CommonMark 0.31.2, spec.commonmark.org/0.31.2:
# 2.4 Backslash escapes, 6.1 Code spans, 6.2 Emphasis and strong emphasis): a quote in prose is also compared without
# a backslash before punctuation, without backticks, and without the * and _ of emphasis, on both sides (not an _
# inside a word, as in snake_case). A code line is compared with every one of them: there they are the code.
ESCAPED = re.compile(r"\\([!-/:-@\[-`{-~])")
EMPHASIS = re.compile(r"(?<!\w)[*_]+|[*_]+(?!\w)")


class Changed(NamedTuple):
    """Among the sources, in the order the task made its calls: a change that ran to this file (an edit or a write
    of `path`), or to any file (path None: an undo, which names a change, not a file). Windows of a file read on
    either side of it are windows of two versions of the file, and are not joined by their line numbers: a window
    whose header has no sha256 (a file too big to hash) says nothing of its version but when it was read."""
    path: str | None


def unfound_quotes(answer: str | None, sources: Iterable[str | Changed | None] | None) -> list[str]:
    """The quoted material in the answer that is in none of the sources, whitespace made single spaces, in the
    order the answer has it, each once. The sources are texts, in the order they were read, and the changes made
    between them (Changed). None for a text is no text: no answer has no quotes, and a source that is None, or no
    sources, is nothing read."""
    if not answer:
        return []
    texts = [text for text in sources or () if text is not None]
    read = ([_source(text) for text in texts if isinstance(text, str)]
            + [("", _joined(run, patch)) for run, patch in _runs(texts)])
    unmarked = None                                 # what was read without Markdown's inline formatting, when needed
    unfound: list[str] = []
    for quote, compared, spans in _quoted(answer):
        quote, compared = _plain(quote), _plain(compared)
        if quote in unfound or not _checkable(compared):
            continue
        key = _fold(compared)
        if spans:                                   # prose: the quote marks around it and its closing stop are its own
            key = _bare(key)
        if _found(key, spans, read):
            continue
        if spans:
            if unmarked is None:
                unmarked = [("\n".join(map(_unmarked, lines.split("\n"))), tuple(map(_unmarked, wholes)))
                            for lines, wholes in read]
            if _found(_bare(_unmarked(key)), spans, unmarked):
                continue
        unfound.append(quote)
    return unfound


def _found(key: str, spans: bool, read: list[tuple[str, tuple[str, ...]]]) -> bool:
    """Whether the key is inside a line of what was read, or, for a quote that may run across line breaks, inside a
    text joined from its lines."""
    return any(key in lines or (spans and any(key in whole for whole in wholes)) for lines, wholes in read)


def _bare(key: str) -> str:
    return key.strip('" ').rstrip(".,;:!?").strip('" ')


def _unmarked(text: str) -> str:
    return _plain(EMPHASIS.sub("", ESCAPED.sub(r"\1", text).replace("`", "")))


def _lines(text: str) -> list[str]:
    """`text`'s lines as the file tools count them (dawnr_agent/files.py, grep -n): split at a line feed only, with
    a carriage return before it part of the line end, and no line after a last line feed. str.splitlines also splits
    at a vertical tab, a form feed, U+2028 and others, which a file's line can hold."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def _quoted(answer: str) -> list[tuple[str, str, bool]]:
    """(text as the answer has it, text as it is compared, whether it may run across a source's line breaks) for
    each piece of quoted material, in order."""
    out: list[tuple[str, str, bool]] = []
    open_fence = ""                                 # the fence of the code block being read; "" outside one
    diff, indent = False, 0                         # whether that block is a diff, and how far its fence is indented
    lines = _lines(answer)
    for at, line in enumerate(lines):
        fenced, marked = FENCE.match(line), MARKERS.match(line)
        if open_fence:
            if (fenced and fenced.group(1)[0] == open_fence[0] and len(fenced.group(1)) >= len(open_fence)
                    and not fenced.group(2).strip()):
                open_fence = ""
            else:
                out.append((line, _diff_line(line, indent) if diff else line, False))
        elif fenced and not (fenced.group(1)[0] == "`" and "`" in fenced.group(2)):   # ```x``` is inline code
            open_fence = fenced.group(1)
            indent = len(line) - len(line.lstrip(" "))
            diff = (fenced.group(2).strip().split(" ")[0].lower() in DIFF_TAGS
                    or _is_diff(lines[at + 1:], fenced, indent))
        elif marked:
            inner = line[marked.end():]
            if not FENCE.match(inner):              # a code block set in a blockquote: its fences are not quotes
                out.append((inner, inner, True))
        else:
            for straight, curly in QUOTED.findall(line):
                passage = straight or curly
                if len(passage.split()) >= WORDS:
                    out.append((passage, passage, True))
    return out


def _is_diff(rest: list[str], fence, indent: int) -> bool:
    """Whether the code block that `fence` opens, whose lines start `rest`, is a diff by what is in it, whatever its
    language tag says (a model leaves the tag off, or names the file's language): a hunk header in it, `@@ -a,b +c,d
    @@`, which no other code starts a line with."""
    open_fence = fence.group(1)
    for line in rest:
        closing = FENCE.match(line)
        if (closing and closing.group(1)[0] == open_fence[0] and len(closing.group(1)) >= len(open_fence)
                and not closing.group(2).strip()):
            return False
        if HUNK.match(line[min(indent, len(line) - len(line.lstrip(" "))):]):
            return True
    return False


def _diff_line(line: str, indent: int) -> str:
    """What a line of a diff block in an answer quotes: a line of either text without its "-", "+" or " "; of a hunk's
    header, its heading; of a line that names files, nothing. The fence's indentation is not the line's
    (CommonMark: spec.commonmark.org/0.31.2/#fenced-code-blocks, up to that many spaces come off each line)."""
    line = line[min(indent, len(line) - len(line.lstrip(" "))):]
    if DIFF_FILES.match(line):
        return ""
    hunk = HUNK_HEAD.match(line)
    if hunk:
        return line[hunk.end():]
    return line[1:] if line[:1] in ("+", "-", " ") else line


def _source(text: str) -> tuple[str, tuple[str, ...]]:
    """A source's lines as they were read, one to a line, and its whole text joined from its lines: each line taken
    without a program's line prefix where the output's lines consistently carry one (_stretches) and a patch's
    marker; whitespace made single spaces in both. A line needs nothing taken off to be searched on its own (what
    is inside the rest of a line is inside the line, and a quote that keeps a prefix or the "+" is found too); the
    prefixes matter where lines are joined, between the end of one and the next. A text with prefixes taken off is
    also joined as it is, for a quote that keeps them."""
    lines = _lines(text)
    stretches = _stretches(lines)
    whole = [joined for stretch in stretches for joined in _joined(stretch, any(map(HUNK.match, stretch)))]
    if len(stretches) != 1 or stretches[0] != lines:
        whole += _joined(lines, any(map(HUNK.match, lines)))
    return "\n".join(_fold(line) for line in lines), tuple(whole)


def _stretches(lines: list[str]) -> list[list[str]]:
    """The lines as stretches of lines one after the other: a run of two lines or more that all carry a program's line
    prefix, with the numbers counting up, is taken without the prefix and cut where a number is not the one after
    the last (grep -n shows the lines that match, which are not one after the other); the lines between such runs
    are a stretch as they are. Prefixes are the output of cat -n and nl (a number and a tab; nl leaves a blank line
    unnumbered), of grep -n on one file (`3:text`, and `3-text` for a context line) and of grep -n on several
    (`path:3:text`). Only where every line of the run has one: a TSV row or a numbered list in a text is its own."""
    out: list[list[str]] = []
    plain: list[str] = []
    i = 0
    while i < len(lines):
        best = max((got for form in (_cat_n, _grep_one, _grep_many) if (got := _follow(lines, i, form))),
                   key=lambda got: got[0], default=None)
        if best is None:
            plain.append(lines[i])
            i += 1
            continue
        if plain:
            out.append(plain)
            plain = []
        i = best[0]
        out += best[1]
    return out + [plain] if plain else out


def _follow(lines: list[str], i: int, form) -> tuple[int, list[list[str]]] | None:
    """(where the run of lines from i that carry this form of prefix ends, its text in stretches), None for a run
    of fewer than two lines."""
    stretches: list[list[str]] = []
    current: list[str] = []
    blanks: list[str] = []
    key = last = None
    end = i
    count = 0
    for j in range(i, len(lines)):
        got = form(lines[j])
        if got is _BLANK and last is not None:
            blanks.append("")
            continue
        if not isinstance(got, tuple) or (last is not None and (got[0] != key or got[1] <= last)):
            break
        key, number, rest = got
        if last is not None and number != last + 1 and current:
            stretches.append(current)
            current, blanks = [], []
        current += blanks + [rest]
        blanks = []
        last, end, count = number, j + 1, count + 1
    if count < 2:
        return None
    return end, stretches + [current]


_BLANK = object()
_GREP_ONE = re.compile(r"(\d{1,15})[:-]")
_GREP_MANY = re.compile(r"(.{1,300}?)[:-](\d{1,15})[:-]")


def _cat_n(line: str):
    """(key, number, text) of a line of cat -n or nl output; _BLANK for the blank line nl leaves unnumbered."""
    number = NUMBER.match(line)
    if number:
        return "", int(number.group(1)), line[number.end():]
    return _BLANK if not line.strip() else None


def _grep_one(line: str):
    number = _GREP_ONE.match(line)
    return ("", int(number.group(1)), line[number.end():]) if number else None


def _grep_many(line: str):
    hit = _GREP_MANY.match(line)
    return (hit.group(1), int(hit.group(2)), line[hit.end():]) if hit else None


def _joined(lines: list[str], patch: bool = False) -> tuple[str, ...]:
    """Lines as one text, each without a patch's one-character marker, and once more each also without a comment's
    marker, where a comment runs on; whitespace made single spaces. Of a patch, the same of each of its two texts
    too: without its "-" lines (the new one), and without its "+" lines (the old one)."""
    texts = [lines] + ([[line for line in lines if line[:1] != "-"], [line for line in lines if line[:1] != "+"]]
                       if patch else [])
    out: list[str] = []
    for text in texts:
        bare = [line[1:] if line[:1] in ("+", "-", " ") else line for line in text]
        uncommented = [line[comment.end():] if (comment := COMMENT.match(line)) else line for line in bare]
        out += [_fold(" ".join(bare)), _fold(" ".join(uncommented))]
    return tuple(out)


def _shown(text: str) -> list[tuple[str, str | None, int, str | None]]:
    """(file, its version, number, text) of each line of a file that this tool's reply shows, without what the tool
    put on it. The version is the sha256 a window's header gives (fs_read gives it for a file it read whole), else
    None, as for a search's hits; a page's mark in a document has None for its text. Nothing for a reply that is
    not a window or a search."""
    lines = _lines(text)
    head = lines[0] if lines else ""
    window, document = WINDOW.match(head), DOCUMENT.match(head)
    if window or document:
        path, start, last = window.group(1, 2, 3) if window else document.group(1, 3, 4)
        version = window.group(4) if window else None
        start, last, body = int(start), int(last), lines[1:]
        if window and body and re.match(rf" *{start}\t", body[0]):        # numbered: each line says which it is
            return [(path, version, int(number.group(1)), line[number.end():]) for line in body
                    if (number := NUMBER.match(line)) and start <= int(number.group(1)) <= last]
        return [(path, version, n, None if document and PAGE.match(line) else line)
                for n, line in enumerate(body[:last - start + 1], start) if not CLIPPED.match(line)]
    if SEARCH.match(head):
        return [(hit.group(1), None, int(hit.group(2)), hit.group(3)) for hit in map(HIT.match, lines[1:]) if hit]
    return []


def _named(changed: str | None, path: str) -> bool:
    """Whether a change to `changed` (as a call named it; None: any file) is a change to the file a header calls
    `path`: the same path, or one that ends with the other after a slash (a header says root and path)."""
    if changed is None:
        return True
    a, b = changed.removeprefix("./").strip("/"), path.removeprefix("./").strip("/")
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


def _runs(texts: list) -> list[tuple[list[str], bool]]:
    """The lines the tools showed of each file, in runs of lines the file has one after the other, wherever each was
    shown (two windows, two hits, a window and a hit); of a line shown twice, the longer (a hit's is stripped, and
    cut at 200 characters). A page's mark keeps the lines on either side of it one after the other. Windows of two
    versions of a file (read before and after an edit, which can move its lines) are not joined; a line of no known
    version (a hit) is joined to every version of its file, and to the other such lines. A change to the file that
    ran between two replies (Changed, among the texts in the order of the calls) makes the replies after it of
    another version, whether or not their headers have a sha256 to say so. With each run, whether it is a patch's
    (the file is named .patch or .diff, or the run has a hunk header)."""
    files: dict[tuple[str, str | None, int], dict[int, str | None]] = {}
    changes: list[str | None] = []
    for text in texts:
        if isinstance(text, Changed):
            changes.append(text.path)
            continue
        for path, version, n, line in _shown(text):
            era = sum(_named(changed, path) for changed in changes)         # how many changes to this file so far
            got = files.setdefault((path, version, era), {})
            if n not in got or len(line or "") > len(got[n] or ""):
                got[n] = line
    for (path, version, era), got in files.items():
        for n, line in (files.get((path, None, era), {}) if version is not None else {}).items():
            if n not in got or len(line or "") > len(got[n] or ""):
                got[n] = line
    runs: list[tuple[list[str], bool]] = []
    for (path, _version, _era), got in files.items():
        last = None
        for n in sorted(got):
            if n - 1 != last:
                runs.append(([], path.lower().endswith((".patch", ".diff"))))
            if got[n] is not None:
                runs[-1][0].append(got[n])
            last = n
    return [(run, patch or any(map(HUNK.match, run))) for run, patch in runs]


def _plain(text: str) -> str:
    return " ".join(text.split())


def _fold(text: str) -> str:
    """Text as it is compared: whitespace single spaces, a Markdown link its text, every quote mark one."""
    return _plain(LINK.sub(r"\1", text.replace('\\"', '"').replace("\\'", "'")).translate(QUOTE_MARKS))


def _checkable(quote: str) -> bool:
    """Whether a quote has something in it to check: a letter or a digit, and four characters that are not spaces."""
    return len(quote) - quote.count(" ") >= 4 and any(c.isalnum() for c in quote)
