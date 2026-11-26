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
header and hints, a document's page marks), and only lines the file has one after the other. A blockquote line or
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
from typing import Iterable

FENCE = re.compile(r"\s*(`{3,}|~{3,})(.*)")          # a code fence, and the rest of its line
MARKERS = re.compile(r"\s*(?:>\s?)+")                # a blockquote line's ">", nested ones too
NUMBER = re.compile(r" *(\d+)\t")                   # fs_read's line number, right-aligned, and its tab
QUOTED = re.compile(r'"([^"]*)"|\u201c([^\u201c\u201d]*)\u201d')
WORDS = 6                                           # a passage in quotes of fewer words is a phrase
# Compared, not shown (2026-11-26: five of the six quotes a 27B's three reviews had reported were copied, and differed
# from what was read only in these): a comment's marker at the start of a line, where a comment runs on; a Markdown
# link, which a reader quotes by its text; quote marks of every style and escaped ones, as one.
COMMENT = re.compile(r"\s*(?:/\*+|\*+/?|//+|#+|--|;+)\s?")
LINK = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")
QUOTE_MARKS = str.maketrans(dict.fromkeys("'\u2018\u2019\u201a\u201b\u2032\u201c\u201d\u201e\u201f\u2033", '"'))
# What the tools show of a file's lines, and around them (dawnr_agent/files.py): an fs_read window's header (the file,
# its first and last line), the same for a document's text, whose pages are marked on lines of their own; a search's
# header, then each hit after its file's name and its number; and a reply cut at its size. Lines a file has one after
# the other are one text however the tools showed them: in two windows, as two hits, a window and a hit.
WINDOW = re.compile(r"(.*): lines (\d+)-(\d+) of \d+, \d+ bytes")
DOCUMENT = re.compile(r"(.*) \(.*\): lines (\d+)-(\d+) of \d+ of its text, \d+ bytes$")
PAGE = re.compile(r"\[page \d+\]$")
SEARCH = re.compile(r"search for .* \(literal, .*\): \d+ matches in \d+ files, \d+ files searched$")
HIT = re.compile(r"(.+?):(\d+): (.*)")
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


def unfound_quotes(answer: str | None, sources: Iterable[str | None] | None) -> list[str]:
    """The quoted material in the answer that is in none of the sources, whitespace made single spaces, in the
    order the answer has it, each once. None for a text is no text: no answer has no quotes, and a source that is
    None, or no sources, is nothing read."""
    if not answer:
        return []
    texts = [text for text in sources or () if text is not None]
    read = [_source(text) for text in texts] + [("", _joined(run, patch)) for run, patch in _runs(texts)]
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


def _quoted(answer: str) -> list[tuple[str, str, bool]]:
    """(text as the answer has it, text as it is compared, whether it may run across a source's line breaks) for
    each piece of quoted material, in order."""
    out: list[tuple[str, str, bool]] = []
    open_fence = ""                                 # the fence of the code block being read; "" outside one
    diff, indent = False, 0                         # whether that block is a diff, and how far its fence is indented
    for line in answer.splitlines():
        fenced, marked = FENCE.match(line), MARKERS.match(line)
        if open_fence:
            if (fenced and fenced.group(1)[0] == open_fence[0] and len(fenced.group(1)) >= len(open_fence)
                    and not fenced.group(2).strip()):
                open_fence = ""
            else:
                out.append((line, _diff_line(line, indent) if diff else line, False))
        elif fenced and not (fenced.group(1)[0] == "`" and "`" in fenced.group(2)):   # ```x``` is inline code
            open_fence = fenced.group(1)
            diff = fenced.group(2).strip().split(" ")[0].lower() in DIFF_TAGS
            indent = len(line) - len(line.lstrip(" "))
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


def _source(text: str) -> tuple[str, tuple[str, str]]:
    """A source's lines as they were read, one to a line, and its whole text with each line taken without fs_read's
    number and tab and a patch's marker; whitespace made single spaces in both. A line needs nothing taken off to
    be searched on its own (what is inside the rest of a line is inside the line, and a quote that keeps the "+" or
    the number is found too); the markers matter where lines are joined, between the end of one and the next."""
    lines = text.splitlines()
    unnumbered = [line[number.end():] if (number := NUMBER.match(line)) else line for line in lines]
    return "\n".join(_fold(line) for line in lines), _joined(unnumbered, any(map(HUNK.match, unnumbered)))


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


def _shown(text: str) -> list[tuple[str, int, str | None]]:
    """(file, number, text) of each line of a file that this tool's reply shows, without what the tool put on it;
    a page's mark in a document has None for its text. Nothing for a reply that is not a window or a search."""
    lines = text.splitlines()
    head = lines[0] if lines else ""
    window, document = WINDOW.match(head), DOCUMENT.match(head)
    if window or document:
        path, start, last = (window or document).group(1, 2, 3)
        start, last, body = int(start), int(last), lines[1:]
        if window and body and re.match(rf" *{start}\t", body[0]):        # numbered: each line says which it is
            return [(path, int(number.group(1)), line[number.end():]) for line in body
                    if (number := NUMBER.match(line)) and start <= int(number.group(1)) <= last]
        return [(path, n, None if document and PAGE.match(line) else line)
                for n, line in enumerate(body[:last - start + 1], start) if not CLIPPED.match(line)]
    if SEARCH.match(head):
        return [(hit.group(1), int(hit.group(2)), hit.group(3)) for hit in map(HIT.match, lines[1:]) if hit]
    return []


def _runs(texts: list[str]) -> list[tuple[list[str], bool]]:
    """The lines the tools showed of each file, in runs of lines the file has one after the other, wherever each was
    shown (two windows, two hits, a window and a hit); of a line shown twice, the longer (a hit's is stripped, and
    cut at 200 characters). A page's mark keeps the lines on either side of it one after the other. With each run,
    whether it is a patch's (the file is named .patch or .diff, or the run has a hunk header)."""
    files: dict[str, dict[int, str | None]] = {}
    for text in texts:
        for path, n, line in _shown(text):
            got = files.setdefault(path, {})
            if n not in got or len(line or "") > len(got[n] or ""):
                got[n] = line
    runs: list[tuple[list[str], bool]] = []
    for path, got in files.items():
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
