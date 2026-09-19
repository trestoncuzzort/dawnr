"""t/doc_test.py -- the docs test themselves.

ROADMAP 14.5 "Docs that are true": TUTORIAL.md, README.md, SYNTAX.md and
SPEC.md must agree with the tool and with each other, and every example in
them must actually run through the tool. This script is the one command
that checks both halves of that bar.

HALF ONE: every `.t` example in the notation, executed.

A markdown file mixes prose with fenced code blocks in several languages
(JSON schema fragments, EBNF, shell). Only some of those blocks are meant
to be fed to the parser verbatim; the rest are illustrative shorthand (an
ellipsis standing in for "more of the same", a placeholder like `Expr`, a
line of English inside a loop body to name an idea before the reader has
the tools to write it for real). Nothing in a markdown file says which is
which, so this script introduces two conventions and this repo's docs are
written to them from tonight on:

  - a fenced block tagged ```t``` holds real notation: a whole task, a
    run of statements, or a bare expression, and it is executed. Which of
    those three it is is not tagged separately; the script tries a task,
    then a spec_fun, then a run of statements, then a bare expression, in
    that order, and the first that consumes the whole block wins. A block
    that is not in ```t``` (bare ``` ```, ```json```, ```ebnf```, ...) is
    read as prose illustration and is not executed -- this is the
    author's call, made once per block by hand, the same way a docstring
    decides what belongs in a doctest and what doesn't.

  - a fenced ```t``` block immediately preceded by its own comment line

        <!-- t: expect error <substring naming the production or rule> -->

    is a DELIBERATELY malformed example: the script asserts parsing it
    raises SurfaceError, and that the error message contains the given
    substring. This is the only way a bad example is allowed to stay bad
    on purpose; every other tagged block must parse clean.

SYNTAX.md gets a second, stronger check, because its whole second half is
built from paired ```json``` blocks (one JSON value per line -- an Expr,
Stmt, SpecFun or var-decl fragment, not a whole task) and a `written:`
line right below holding the same things in the human notation, separated
by " . " (a middle dot in the file). The script parses every backtick item
on a `written:` line/paragraph and compares it, position for position,
against the JSON line above it: this is what makes SYNTAX.md's claim that
its own notation matches its own JSON a checked claim and not an assertion.
A `written:` item containing the literal ellipsis character is shorthand
("invariant ... decreases ..."), not a fourth grammar the parser must
support, and is skipped, counted, and reported, never silently dropped.

A ```json``` block that IS a whole task (has "t"/"name"/"body") is instead
run through check_wf and must come back well-formed.

HALF TWO: the docs' claims about the notation, checked against surface.py's
own tables, so a sentence that drifts from the code fails this test instead
of sitting there quietly wrong. See FACTS below.

Usage:
    python3 doc_test.py            # run everything, exit 0 iff clean
    python3 doc_test.py -v         # also print every block's verdict
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import surface  # noqa: E402

# check_wf is landing tonight in its own module (t/check_wf.py); until that
# lands this reaches it where it lives today. Either way this is the one
# place doc_test.py names the import, so the day check_wf.py exists this
# needs no other change.
try:
    from check_wf import check_wf  # type: ignore
except ImportError:
    from fuzz_lower import check_wf  # type: ignore


# ===========================================================================
# Fenced-block extraction.
# ===========================================================================

_FENCE_OPEN = re.compile(r"^```([A-Za-z0-9_-]*)\s*$")
_FENCE_CLOSE = re.compile(r"^```\s*$")
_EXPECT_ERROR = re.compile(r"^<!--\s*t:\s*expect error\s+(.+?)\s*-->\s*$")


class Block:
    __slots__ = ("lang", "text", "start_line", "expect_error")

    def __init__(self, lang, text, start_line, expect_error):
        self.lang = lang
        self.text = text
        self.start_line = start_line
        self.expect_error = expect_error


def extract_blocks(path: Path) -> list:
    lines = path.read_text().splitlines()
    blocks = []
    i = 0
    prev_nonblank = None
    while i < len(lines):
        m = _FENCE_OPEN.match(lines[i])
        if not m:
            if lines[i].strip():
                prev_nonblank = lines[i]
            i += 1
            continue
        lang = m.group(1)
        body = []
        j = i + 1
        while j < len(lines) and not _FENCE_CLOSE.match(lines[j]):
            body.append(lines[j])
            j += 1
        expect = None
        if prev_nonblank is not None:
            em = _EXPECT_ERROR.match(prev_nonblank)
            if em:
                expect = em.group(1)
        blocks.append(Block(lang, "\n".join(body), i + 1, expect))
        i = j + 1
        prev_nonblank = None
    return blocks


# ===========================================================================
# The four grammar entry points, tried in order. A parse "wins" a tier
# only if it consumes the whole block (no trailing tokens).
# ===========================================================================

def parse_spec_fun(text: str) -> dict:
    p = surface.Parser(text)
    fn = p.spec_fun()
    if not p.at("eof"):
        raise surface.SurfaceError("trailing text after spec_fun")
    return fn


def parse_stmts(text: str) -> list:
    p = surface.Parser(text)
    if p.at("eof"):
        raise surface.SurfaceError("empty statement block")
    out = []
    while not p.at("eof"):
        out.append(p.stmt())
    return out


# Tier name -> (callable, what a success looks like).
TIERS = [
    ("task", surface.parse),
    ("spec_fun", parse_spec_fun),
    ("stmts", parse_stmts),
    ("expr", surface.parse_expr),
]


def parse_t_block(text: str):
    """Try each tier in order; return (tier_name, parsed) on the first
    that consumes the whole block. Raises the LAST tier's SurfaceError if
    none succeed (the most informative one: expr is the most permissive
    grammar, so its failure is usually the one closest to the real
    problem)."""
    last_exc = None
    for name, fn in TIERS:
        try:
            return name, fn(text)
        except surface.SurfaceError as exc:
            last_exc = exc
            continue
    raise last_exc


# ===========================================================================
# SYNTAX.md's json/written pairing.
# ===========================================================================

_BACKTICK = re.compile(r"`([^`]+)`")
_WRITTEN_START = re.compile(r"^written:\s*(.*)$")


_DECODER = json.JSONDecoder()


def json_fragments(block_text: str):
    """A SYNTAX.md ```json``` block holds one or more top-level JSON
    values, each possibly spanning several physical lines (an `args` list
    that wraps). Walk the block with a raw JSON decoder, consuming one
    value at a time; a stretch that is not valid JSON on its own (a
    schema placeholder like `...Expr...`) is skipped a line at a time
    from the error position until decoding resumes. Returns
    (fragments, skipped_line_count)."""
    frags = []
    skipped = 0
    s = block_text
    i, n = 0, len(s)
    while i < n:
        while i < n and s[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        try:
            val, end = _DECODER.raw_decode(s, i)
            frags.append(val)
            i = end
        except json.JSONDecodeError as exc:
            skipped += 1
            nl = s.find("\n", max(exc.pos, i))
            if nl == -1:
                break
            i = nl + 1
    return frags, skipped


def written_paragraph(lines: list, after_idx: int):
    """Starting just after a fenced block ending at `lines[after_idx]`,
    read the `written:` paragraph: the first non-blank line must start
    with "written:"; any immediately-following lines that themselves
    start with a backtick are continuations (SYNTAX.md wraps long lists).
    Returns (text, next_idx) or (None, after_idx) if there is none."""
    k = after_idx + 1
    if k >= len(lines) or not lines[k].strip():
        return None, after_idx
    m = _WRITTEN_START.match(lines[k].strip())
    if not m:
        return None, after_idx
    text = m.group(1)
    k += 1
    while k < len(lines) and lines[k].strip().startswith("`"):
        text += " " + lines[k].strip()
        k += 1
    return text, k - 1


def parse_written_item(item: str):
    """A written-line item is either a bare expression or one statement.
    A statement's trailing `;` is optional in the grammar itself (only
    assign/var/return ever consume one; if/while never do), so try the
    text as written before trying it with a `;` appended."""
    try:
        return "expr", surface.parse_expr(item)
    except surface.SurfaceError:
        pass
    try:
        return "stmt", surface.parse_stmt(item)
    except surface.SurfaceError:
        if item.rstrip().endswith(";"):
            raise
    return "stmt", surface.parse_stmt(item + ";")


# ===========================================================================
# Per-file checking.
# ===========================================================================

class FileReport:
    def __init__(self, path):
        self.path = path
        self.blocks = 0
        self.parsed = 0
        self.well_formed = 0
        self.expected_errors_matched = 0
        self.skipped = 0
        self.failures = []  # list of str

    def fail(self, where, msg):
        self.failures.append("%s:%s: %s" % (self.path, where, msg))

    def __str__(self):
        return ("%s: %d block(s), %d parsed, %d well-formed, "
                "%d expected-error(s) matched, %d skipped, %d failure(s)"
                % (self.path, self.blocks, self.parsed, self.well_formed,
                   self.expected_errors_matched, self.skipped,
                   len(self.failures)))


def check_t_or_json_block(rep: FileReport, b: Block):
    where = "%s:%d" % (rep.path.name, b.start_line)
    if b.expect_error is not None:
        # Every tier must fail (this text is not valid t under ANY of the
        # four entry points), and at least one tier's message must name
        # what the doc says it names. Different tiers can fail on
        # different tokens (e.g. `if` alone is both a statement prefix
        # and an expression's ternary prefix, so a missing `else` reads
        # as "expected 'else'" from one tier and "expected 'then'" from
        # another); it is the doc's claim, not the cascade's pick, that
        # is under test here.
        errs = []
        for name, fn in TIERS:
            try:
                fn(b.text)
            except surface.SurfaceError as exc:
                errs.append(str(exc))
            else:
                rep.fail(where, "expected error containing %r, but the "
                          "block parsed as a %s" % (b.expect_error, name))
                return
        if any(b.expect_error.lower() in e.lower() for e in errs):
            rep.expected_errors_matched += 1
        else:
            rep.fail(where, "expected an error containing %r, got: %s"
                      % (b.expect_error, "; ".join(errs)))
        return

    if b.lang == "t":
        try:
            tier, parsed = parse_t_block(b.text)
        except surface.SurfaceError as exc:
            rep.fail(where, "does not parse: %s" % exc)
            return
        rep.parsed += 1
        if tier == "task":
            errs = check_wf(parsed)
            if errs:
                rep.fail(where, "task is not well-formed: %s" % "; ".join(errs))
            else:
                rep.well_formed += 1
        else:
            # A bare stmt/expr/spec_fun has no task-level well-formedness
            # to check (no params/returns to type against); parsing clean
            # is the whole claim the doc makes about it.
            rep.well_formed += 1
        return

    if b.lang == "json":
        whole = b.text.strip()
        try:
            val = json.loads(whole)
        except (json.JSONDecodeError, ValueError):
            return  # SYNTAX.md multi-fragment block; handled separately
        if isinstance(val, dict) and {"t", "name", "body"} <= val.keys():
            rep.parsed += 1
            errs = check_wf(val)
            if errs:
                rep.fail(where, "task is not well-formed: %s" % "; ".join(errs))
            else:
                rep.well_formed += 1


def check_syntax_written_pairs(rep: FileReport, path: Path):
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        m = _FENCE_OPEN.match(lines[i])
        if not m or m.group(1) != "json":
            i += 1
            continue
        start = i
        j = i + 1
        body = []
        while j < len(lines) and not _FENCE_CLOSE.match(lines[j]):
            body.append(lines[j])
            j += 1
        block_text = "\n".join(body)
        frags, skipped = json_fragments(block_text)
        rep.skipped += skipped
        rep.blocks += len(frags)
        wtext, wend = written_paragraph(lines, j)
        if wtext is not None:
            items = _BACKTICK.findall(wtext)
            where = start + 1
            for idx, item in enumerate(items):
                if "\u2026" in item or "..." in item:
                    rep.skipped += 1
                    continue
                try:
                    _, parsed_item = parse_written_item(item)
                except surface.SurfaceError as exc:
                    rep.fail(where, "written item %r does not parse: %s"
                              % (item, exc))
                    continue
                rep.parsed += 1
                if idx < len(frags):
                    if surface.canon(parsed_item) != surface.canon(frags[idx]):
                        rep.fail(where,
                                  "written item %r parses to %s, "
                                  "JSON line says %s"
                                  % (item, surface.canon(parsed_item),
                                     surface.canon(frags[idx])))
                    else:
                        rep.well_formed += 1
        i = j + 1


def check_file(path: Path, is_syntax: bool) -> FileReport:
    rep = FileReport(path)
    blocks = extract_blocks(path)
    for b in blocks:
        if b.lang not in ("t", "json"):
            continue
        rep.blocks += 1
        check_t_or_json_block(rep, b)
    if is_syntax:
        check_syntax_written_pairs(rep, path)
    return rep


# ===========================================================================
# HALF TWO: facts the docs state about the notation, checked against
# surface.py's own tables. Each entry is (doc file, sentence it comes from,
# claimed value, actual value) -- a mismatch is a stale sentence.
# ===========================================================================

def _read(name: str) -> str:
    return (HERE / name).read_text()


def gather_facts():
    """Returns a list of (label, claimed, actual, file) tuples. A caller
    reports every one where claimed != actual as a stale sentence."""
    facts = []

    tutorial = _read("TUTORIAL.md")
    syntax = _read("SYNTAX.md")

    # ROADMAP 14.5 left this open by name on 2026-09-11: the aggregate counts in SYNTAX.md's introduction were
    # cross-checked only by `surface.py --check`, which the test stage runs and this file did not, so a count
    # that drifted sat on the page unchallenged. One of them had: it said "the 23 committed tasks in tasks/"
    # while tasks/ held 35 (2026-09-19). The corpus-wide round-trip numbers still belong to surface.py --check,
    # which regenerates them; what this can own is every count of something on disk right now.
    import tasks_io
    committed = len(tasks_io.load_dir(HERE / "tasks"))
    m = re.search(r"The corpus is the (\d+) committed tasks in", syntax)
    facts.append((
        "SYNTAX.md: \"the %s committed tasks in tasks/\"" % (m.group(1) if m else "?"),
        int(m.group(1)) if m else None, committed, "SYNTAX.md"))

    # TUTORIAL lesson 0's claim about parsing: as of 2026-09-04 (SYNTAX.md
    # "since 2026-09-04 that tree also has a surface syntax") the notation
    # IS parsed by surface.py, so a claim that "nothing parses the pretty
    # form" is stale the moment it is still on the page.
    claims_nothing_parses = "nothing parses the pretty form" in tutorial
    facts.append((
        "TUTORIAL.md lesson 0: \"nothing parses the pretty form\"",
        claims_nothing_parses, False, "TUTORIAL.md"))

    # "t has exactly four" statements (lesson 4). The Stmt grammar today:
    # assign, if, var, while, return.
    stmt_kinds = {"assign", "if", "var", "while", "return"}
    m = re.search(r"t has exactly (\w+),?\s*and you know two\s+already",
                  tutorial)
    claimed_n = _word_to_int(m.group(1)) if m else None
    facts.append((
        "TUTORIAL.md lesson 4: \"t has exactly %s\" statements"
        % (m.group(1) if m else "?"),
        claimed_n, len(stmt_kinds), "TUTORIAL.md"))

    # SYNTAX.md "17 polymorphic seq operators" for the string library:
    # surface.STR_METHODS (postfix members) plus tostr (a plain call).
    m = re.search(r"(\d+)\s+polymorphic\s+seq\s+operators", syntax)
    claimed_17 = int(m.group(1)) if m else None
    facts.append((
        "SYNTAX.md \"the string library\": operator count",
        claimed_17, len(surface.STR_METHODS) + 1, "SYNTAX.md"))

    return facts


_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
          "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def _word_to_int(w):
    return _WORDS.get(w.lower())


def run_facts(verbose: bool) -> int:
    failures = 0
    for label, claimed, actual, fname in gather_facts():
        ok = claimed == actual
        if not ok:
            failures += 1
            print("STALE: %s -- doc says %r, tool says %r (%s)"
                  % (label, claimed, actual, fname))
        elif verbose:
            print("ok: %s (%r)" % (label, claimed))
    return failures


# ===========================================================================
# Main.
# ===========================================================================

TARGETS = [
    ("TUTORIAL.md", False),
    ("README.md", False),
    ("SYNTAX.md", True),
    ("SPEC.md", False),
]


def main() -> int:
    verbose = "-v" in sys.argv[1:]
    total_failures = 0

    for name, is_syntax in TARGETS:
        path = HERE / name
        rep = check_file(path, is_syntax)
        print(rep)
        for f in rep.failures:
            print("  FAIL: %s" % f)
        total_failures += len(rep.failures)

    fact_failures = run_facts(verbose)
    total_failures += fact_failures

    print("=== doc_test.py: %d failure(s) ===" % total_failures)
    return 1 if total_failures else 0


if __name__ == "__main__":
    sys.exit(main())
