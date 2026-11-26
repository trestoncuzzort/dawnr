"""test_dawnr_quotes.py: dawnr_agent/quotes.py, the quotes in an answer that are in nothing the session read.

What must hold: a code line that drops a clause from the line it stands for is reported, and a line copied exactly
is not, whether it was read in a patch (with its "+" or without), an fs_read window (with its line numbers or
without) or an fs_search hit; a code line is looked for one source line at a time, a blockquote line and a passage
of six words or more in double quotes across the source's line breaks too, and across lines a file has one after
the other wherever the tools showed them (two windows, two search hits, a document's page break), never across
two files or lines apart; a passage of either text of a patch over a changed line is found; a diff block's line is
compared without its marker and its syntax is not a quote; prose is found with Markdown's emphasis, code spans and
escapes or without them, a code line only with every character; a passage of fewer than six words, and a
line with nothing to check in it (punctuation, an ellipsis, fewer than four characters), is never reported; what is
reported comes in the order of the answer, once each; None for the answer, for a source or for the sources is no
text. Standard library only.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dawnr_agent.quotes import unfound_quotes  # noqa: E402

# The real case: a patch excerpt as the session read it, and the line an answer showed in a code block as the
# patch's own. The patch tests hit.mFraction and the contact on two lines; the answer's `if` has the contact alone.
PATCH = ("+\t\t\tif (hit.mFraction < 0.0f || hit.mFraction > 1.0f\n"
         "+\t\t\t\t|| mContactManager.HasContactInCurrentStep(inBody.GetID(), hit.mSubShapeID1, sensor->GetID(), hit.mSubShapeID2))\n"
         "+\t\t\t\tcontinue;\n")
CLAIMED = "if (mContactManager.HasContactInCurrentStep(inBody.GetID(), hit.mSubShapeID1, sensor->GetID(), hit.mSubShapeID2))"

# The same patch read with fs_read: its header, then each line after a right-aligned number and a tab.
READ_PATCH = ("here/sensor.patch: lines 41-43 of 60, 2391 bytes, sha256 5d41402abc4b\n"
              + "".join(f"  {n}\t{line}\n" for n, line in enumerate(PATCH.splitlines(), 41))
              + "[lines 44-60 not shown; read again with \"start\": 44]")

READ = ("here/settings.py: lines 10-15 of 120, 3954 bytes, sha256 9f86d081884c\n"
        "  10\tdef load(path):\n"
        "  11\t    \"\"\"The settings in path, or None when the file is missing.\"\"\"\n"
        "  12\t    if not os.path.exists(path):\n"
        "  13\t        return None\n"
        "  14\t    with open(path, encoding=\"utf-8\") as f:\n"
        "  15\t        return parse(f.read())\n"
        "[lines 16-120 not shown; read again with \"start\": 16]")

DOC = ("here/README.md: lines 1-4 of 4, 104 bytes, sha256 2c26b46b68ff\n"
       "   1\t# Cache\n"
       "   2\t\n"
       "   3\tThe cache is cleared only when the person\n"
       "   4\truns clean, and never on its own.")

SEARCH = ("search for 'HasContactInCurrentStep' in every root (literal, exact case): 1 matches in 1 files, 1408 files "
          "searched\n"
          "here/src/sensor.cpp:1261: || mContactManager.HasContactInCurrentStep(inBody.GetID(), hit.mSubShapeID1, "
          "sensor->GetID(), hit.mSubShapeID2))")


def code(*lines: str, tag: str = "") -> str:
    """An answer that is one fenced code block holding these lines."""
    return f"```{tag}\n" + "\n".join(lines) + "\n```\n"


class CodeLineTest(unittest.TestCase):
    def test_a_condition_with_a_clause_dropped_is_reported_and_the_line_after_it_is_found(self):
        answer = "The sensor skips a body it is already touching:\n\n" + code(CLAIMED, "    continue;", tag="cpp")
        self.assertEqual(unfound_quotes(answer, [PATCH]), [CLAIMED])
        self.assertEqual(unfound_quotes(answer, [READ_PATCH]), [CLAIMED])

    def test_lines_copied_from_a_patch_are_found_without_its_plus_and_in_other_whitespace(self):
        answer = code("if (hit.mFraction < 0.0f  ||  hit.mFraction > 1.0f",
                      "    || mContactManager.HasContactInCurrentStep(inBody.GetID(), hit.mSubShapeID1, sensor->GetID(), "
                      "hit.mSubShapeID2))",
                      "\tcontinue;", tag="cpp")
        self.assertEqual(unfound_quotes(answer, [PATCH]), [])
        self.assertEqual(unfound_quotes(answer, [READ_PATCH]), [])

    def test_lines_copied_from_a_numbered_fs_read_window_are_found_and_a_changed_one_is_not(self):
        answer = ("`load` gives None for a missing file:\n\n"
                  + code("def load(path):", "    if not os.path.exists(path):", "        return None",
                         '    with open(path, encoding="utf-8") as f:', tag="python"))
        self.assertEqual(unfound_quotes(answer, [READ]), [])
        changed = code("def load(path):", "    if os.path.isfile(path) is False:", "        return None")
        self.assertEqual(unfound_quotes(changed, [READ]), ["if os.path.isfile(path) is False:"])

    def test_a_line_copied_from_an_fs_search_hit_is_found(self):
        answer = code("|| mContactManager.HasContactInCurrentStep(inBody.GetID(), hit.mSubShapeID1, sensor->GetID(), "
                      "hit.mSubShapeID2))")
        self.assertEqual(unfound_quotes(answer, [SEARCH]), [])
        self.assertEqual(unfound_quotes(code(CLAIMED), [SEARCH]), [CLAIMED])

    def test_a_code_line_is_looked_for_in_one_source_line_at_a_time(self):
        # Two of the patch's lines run into one: in the patch's text, on none of its lines. As a blockquote line the
        # same words are found, the "+" before each line taken off where the lines are joined.
        joined = ("if (hit.mFraction < 0.0f || hit.mFraction > 1.0f || mContactManager.HasContactInCurrentStep("
                  "inBody.GetID(), hit.mSubShapeID1, sensor->GetID(), hit.mSubShapeID2))")
        self.assertEqual(unfound_quotes(code(joined), [PATCH]), [joined])
        self.assertEqual(unfound_quotes("> " + joined + "\n", [PATCH]), [])

    def test_a_line_quoted_with_its_patch_marker_or_its_fs_read_number_is_found_too(self):
        diff = code("+\t\t\t\tcontinue;", "+\t\t\tif (hit.mFraction < 0.0f || hit.mFraction > 1.0f", tag="diff")
        self.assertEqual(unfound_quotes(diff, [PATCH]), [])
        self.assertEqual(unfound_quotes(code("  12\t    if not os.path.exists(path):"), [READ]), [])

    def test_a_line_with_nothing_to_check_is_never_reported(self):
        answer = code("}", "});", "...", "\u2026", "  // ...", "[ ]", "x=1", "end", "-----", "", "   ", tag="js")
        self.assertEqual(unfound_quotes(answer, [PATCH]), [])
        self.assertEqual(unfound_quotes(answer, []), [])
        self.assertEqual(unfound_quotes(code("else"), [PATCH]), ["else"])          # four characters: checked

    def test_tilde_fences_longer_fences_and_an_unclosed_fence_hold_code(self):
        answer = ("~~~python\nreturn parse(f.read())\n~~~\n\n"
                  "````markdown\n```\nreturn parse(path)\n````\n\n"
                  "```\nraise SettingsError(path)\n")
        self.assertEqual(unfound_quotes(answer, [READ]), ["return parse(path)", "raise SettingsError(path)"])

    def test_a_line_with_backticks_after_its_three_is_not_a_fence(self):
        answer = '```inline``` is code, and the docs say "a stale cache is rebuilt in the background"\nreturn cache.get(key)\n'
        self.assertEqual(unfound_quotes(answer, [DOC]), ["a stale cache is rebuilt in the background"])


class ProseQuoteTest(unittest.TestCase):
    def test_a_blockquote_line_is_found_across_the_source_lines_and_one_not_read_is_reported(self):
        answer = ("The README is plain about it:\n\n"
                  "> The cache is cleared only when the person runs clean, and never on its own.\n\n"
                  "and line for line:\n\n"
                  "> The cache is cleared only when the person\n"
                  ">   runs clean, and never on its own.\n\n"
                  "It does not say what a later version claims:\n\n"
                  "> The cache is cleared every night at midnight.\n")
        self.assertEqual(unfound_quotes(answer, [DOC]), ["The cache is cleared every night at midnight."])

    def test_a_passage_in_quotes_is_found_across_the_source_lines_and_one_not_read_is_reported(self):
        answer = ('It says the cache is "cleared only when the person runs clean, and never on its own" and that '
                  '"a stale cache is rebuilt in the background".\n')
        self.assertEqual(unfound_quotes(answer, [DOC]), ["a stale cache is rebuilt in the background"])

    def test_curly_quotes_are_quotes(self):
        answer = ("It says the cache is \u201ccleared only when the person runs clean, and never on its own\u201d and "
                  "that \u201ca stale cache is rebuilt in the background\u201d.\n")
        self.assertEqual(unfound_quotes(answer, [DOC]), ["a stale cache is rebuilt in the background"])

    def test_a_passage_of_fewer_than_six_words_is_not_a_quote(self):
        self.assertEqual(unfound_quotes('The flag is "--force" and the message "cache is not ready yet".', [DOC]), [])
        self.assertEqual(unfound_quotes('The message is "the cache is not ready yet".', [DOC]),
                         ["the cache is not ready yet"])

    def test_a_fence_inside_a_blockquote_is_not_a_quote(self):
        self.assertEqual(unfound_quotes("> ```cpp\n> continue;\n> ```\n", [PATCH]), [])

    def test_a_blockquote_line_with_nothing_to_check_is_not_reported(self):
        answer = "> The cache is cleared only when the person\n> ...\n> [...]\n>\n"
        self.assertEqual(unfound_quotes(answer, [DOC]), [])


class ResultTest(unittest.TestCase):
    def test_an_answer_with_no_quotes_gives_nothing(self):
        self.assertEqual(unfound_quotes("", [PATCH]), [])
        self.assertEqual(unfound_quotes("## What changed\n\nThe check now tests `hit.mFraction` before the contact; "
                                        "nothing else changed.\n", []), [])

    def test_with_nothing_read_every_quote_is_reported(self):
        answer = ('It says "a stale cache is rebuilt in the background".\n\n'
                  + code(CLAIMED, "    continue;")
                  + "\n> The cache is cleared every night at midnight.\n")
        self.assertEqual(unfound_quotes(answer, []),
                         ["a stale cache is rebuilt in the background", CLAIMED, "continue;",
                          "The cache is cleared every night at midnight."])

    def test_what_is_reported_comes_in_the_order_of_the_answer(self):
        answer = ("> The cache is cleared every night at midnight.\n\n"
                  + code("return cache.get(key)", "return None")
                  + '\nIt also says "a stale cache is rebuilt in the background".\n')
        self.assertEqual(unfound_quotes(answer, [DOC, READ]),
                         ["The cache is cleared every night at midnight.", "return cache.get(key)",
                          "a stale cache is rebuilt in the background"])

    def test_a_quote_is_reported_once(self):
        answer = (code("return cache.get(key)", "return None")
                  + "\nand again, indented:\n\n"
                  + code("        return cache.get(key)", "    raise KeyError(key)", "return   cache.get(key)", tag="python")
                  + "\n> return cache.get(key)\n")
        self.assertEqual(unfound_quotes(answer, [READ]), ["return cache.get(key)", "raise KeyError(key)"])

    def test_the_sources_may_be_any_iterable_of_texts(self):
        answer = code(CLAIMED, "continue;")
        self.assertEqual(unfound_quotes(answer, (text for text in [PATCH])), [CLAIMED])
        self.assertEqual(unfound_quotes(answer, iter([DOC, PATCH])), [CLAIMED])


class LiveReviewTest(unittest.TestCase):
    """Quotes a 27B wrote in three reviews of one task (2026-11-26), every one copied from what it read and every one
    reported before: a comment that runs over two lines, a sentence set in quotes inside a blockquote, a sentence whose
    source has Markdown links, and a sentence whose quotes inside it are another style, with the period inside."""

    def test_a_comment_quoted_across_two_lines_is_found_without_the_comment_markers(self):
        patch = ("here/golden.patch: lines 256-257 of 500, 27580 bytes, sha256 94438ada9f84\n"
                 " 256\t+\t\t\t// Replay the base resolver's travel shortening, without modifying any body\n"
                 " 257\t+\t\t\t// or its original CCD record. Observe the fraction at each body's own turn.\n")
        scenes = ("here/scenes.py: lines 110-111 of 188, 10762 bytes, sha256 0a1b2c3d4e5f\n"
                  " 110\t    # A long thin box starts horizontal. Rotation at integration places its tip\n"
                  " 111\t    # in the sensor before the positive-X cast. Translation then separates it.\n")
        answer = ('It states "Replay the base resolver\'s travel shortening, without modifying any body or its original '
                  'CCD record." and the scene says "Rotation at integration places its tip in the sensor before the '
                  'positive-X cast. Translation then separates it."')
        self.assertEqual(unfound_quotes(answer, [patch, scenes]), [])

    def test_a_blockquote_set_in_quote_marks_is_found(self):
        brief = ("here/instruction.md: lines 2-2 of 8, 1945 bytes, sha256 26b5c67b4b06\n"
                 "2\t**Task description.** A fast body can pass through a sensor. Report every static sensor the body "
                 "really touches on its way, as an ordinary contact: from the step it is touched, it gets exactly what "
                 "the listener gives any other contact. Change nothing else.\n")
        answer = ('> "Report every static sensor the body really touches on its way, as an ordinary contact: from the '
                  'step it is touched, it gets exactly what the listener gives any other contact."')
        self.assertEqual(unfound_quotes(answer, [brief]), [])

    def test_a_sentence_whose_source_has_markdown_links_is_found_by_the_links_text(self):
        rationale = ("here/docs/rationale.md: lines 150-150 of 154, 22834 bytes, sha256 7c4a8d09ca37\n"
                     "150\tThe [component matrix](check-evidence/case-matrix.tsv#L1-L25) predates the rotated-start "
                     "fix. The [contact traces](check-evidence/contact-proof.log#L1-L9) include the accepted and "
                     "rejected discrete controls.\n")
        answer = '- Line 150: "The component matrix predates the rotated-start fix. The contact traces include the accepted and rejected discrete controls."'
        self.assertEqual(unfound_quotes(answer, [rationale]), [])

    def test_quote_marks_of_another_style_and_a_period_inside_the_closing_quote_are_found(self):
        checks = ("here/tests/checks.toml: lines 133-133 of 306, 13933 bytes, sha256 e3b0c44298fc\n"
                  '133\treference = { path = "AGENTS.md", line = 79, quote = "- User-visible changes go into '
                  '`Docs/ReleaseNotes.md` (under \\"Unreleased changes\\"); breaking API changes also go elsewhere." }\n')
        answer = "Required by: “User-visible changes go into `Docs/ReleaseNotes.md` (under 'Unreleased changes').”"
        self.assertEqual(unfound_quotes(answer, [checks]), [])

    def test_the_line_with_a_clause_dropped_is_still_reported_with_all_of_this_in_place(self):
        answer = f"```\n{CLAIMED}\n    continue;\n```\nAs the patch says: \"without modifying any body or its original CCD record.\""
        patch = (PATCH + "+\t\t\t// Replay the base resolver's travel shortening, without modifying any body\n"
                 "+\t\t\t// or its original CCD record.\n")
        self.assertEqual(unfound_quotes(answer, [patch]), [CLAIMED])


# One file's lines as the tools show them (dawnr_agent/files.py): fs_search's hits, each after the file's name and
# its number; two fs_read windows, each after its header and with its line numbers, the first with the hint where
# to go on; the same two windows as fs_read gave them before reads were numbered; a document's text with its pages
# marked; and an edit's window of the lines it left.
CACHE = ["# Cache", "", "The cache is cleared only when the person", "runs clean, and never on its own.", "",
         "## Rebuilding", "", "", "A stale cache is rebuilt in the background."]
BOTH = "> The cache is cleared only when the person runs clean, and never on its own.\n"
HITS = ("search for 'the' in here (literal, ignoring case): 3 matches in 1 files, 4 files searched\n"
        "here/docs/cache.md:3: The cache is cleared only when the person\n"
        "here/docs/cache.md:4: runs clean, and never on its own.\n"
        "here/docs/cache.md:9: A stale cache is rebuilt in the background.")


def window(path: str, lines: list, start: int, last: int, numbered: bool = True, sha: str = "0f1e2d3c4b5a") -> str:
    """fs_read's reply for lines start..last of a file of these lines, whose sha256 starts with `sha`."""
    shown = lines[start - 1:last]
    body = "\n".join(f"{n:>{len(str(last))}}\t{line}" if numbered else line for n, line in enumerate(shown, start))
    more = f"\n[lines {last + 1}-{len(lines)} not shown; read again with \"start\": {last + 1}]" if last < len(lines) else ""
    return f"{path}: lines {start}-{last} of {len(lines)}, 310 bytes, sha256 {sha}\n{body}{more}"


class ReadFormatTest(unittest.TestCase):
    """What the tools put around and between the lines of a file is not in a quote of them: a passage that runs
    over two lines a file has one after the other is found wherever the tools showed those lines."""

    def test_a_passage_over_two_adjacent_search_hits_is_found_and_over_two_far_apart_is_not(self):
        self.assertEqual(unfound_quotes(BOTH, [HITS]), [])
        apart = 'It says "runs clean, and never on its own. A stale cache is rebuilt in the background".'
        self.assertEqual(unfound_quotes(apart, [HITS]), ["runs clean, and never on its own. A stale cache is rebuilt "
                                                         "in the background"])

    def test_a_passage_over_two_windows_of_one_file_is_found_in_either_order_numbered_or_not(self):
        first, second = window("here/docs/cache.md", CACHE, 1, 3), window("here/docs/cache.md", CACHE, 4, 9)
        self.assertEqual(unfound_quotes(BOTH, [first]), ["The cache is cleared only when the person runs clean, and "
                                                         "never on its own."])
        self.assertEqual(unfound_quotes(BOTH, [first, second]), [])
        self.assertEqual(unfound_quotes(BOTH, [second, PATCH, first]), [])
        bare = [window("here/docs/cache.md", CACHE, 1, 3, numbered=False),
                window("here/docs/cache.md", CACHE, 4, 9, numbered=False)]
        self.assertEqual(unfound_quotes(BOTH, bare), [])

    def test_a_window_and_a_search_hit_of_the_next_line_are_one_text(self):
        hit = ("search for 'clean' in here/docs (literal, exact case): 1 matches in 1 files, 2 files searched\n"
               "here/docs/cache.md:4: runs clean, and never on its own.")
        self.assertEqual(unfound_quotes(BOTH, [window("here/docs/cache.md", CACHE, 1, 3), hit]), [])

    def test_lines_of_two_files_or_of_one_file_not_one_after_the_other_are_not_joined(self):
        other = ["runs clean, and never on its own."]
        self.assertEqual(unfound_quotes(BOTH, [window("here/docs/cache.md", CACHE, 1, 3),
                                               window("here/docs/other.md", other, 1, 1)]),
                         ["The cache is cleared only when the person runs clean, and never on its own."])
        skipped = CACHE[:3] + ["(a line between)"] + CACHE[3:]
        self.assertEqual(unfound_quotes(BOTH, [window("here/docs/cache.md", skipped, 1, 3),
                                               window("here/docs/cache.md", skipped, 5, 10)]),
                         ["The cache is cleared only when the person runs clean, and never on its own."])

    def test_windows_of_the_file_before_and_after_an_edit_are_not_joined(self):
        # Lines 1-3 read, the first line taken out, lines 4-5 read: the file's line 4 is now what was line 5. Line 3
        # then line 5 of the old file is in neither file; the two windows have two sha256s, a hit has none.
        old = CACHE[:3] + ["(a line between)"] + CACHE[3:]
        new = old[1:]
        reads = [window("here/docs/cache.md", old, 1, 3, sha="aaaaaaaaaaaa"),
                 window("here/docs/cache.md", new, 4, 5, sha="bbbbbbbbbbbb")]
        self.assertEqual(new[3], "runs clean, and never on its own.")
        self.assertEqual(unfound_quotes(BOTH, reads), ["The cache is cleared only when the person runs clean, and "
                                                       "never on its own."])
        self.assertEqual(unfound_quotes(BOTH, [reads[0], HITS]), [])        # a hit joins any window of its file

    def test_a_passage_over_a_page_break_of_a_document_is_found(self):
        pdf = ("here/docs/cache.pdf (pdf, 2 pages): lines 1-4 of 4 of its text, 20480 bytes\n"
               "[page 1]\nThe cache is cleared only when the person\n[page 2]\nruns clean, and never on its own.")
        self.assertEqual(unfound_quotes(BOTH, [pdf]), [])

    def test_a_passage_from_an_edit_window_is_found(self):
        # A guard, found before the change above too: an edit's window has its header before the lines and its
        # hint after them, and nothing on them or between them.
        edited = "lines 2-5 of 9 are now:\n\nThe cache is cleared only when the person\nruns clean, or on a schedule.\n"
        self.assertEqual(unfound_quotes("> The cache is cleared only when the person runs clean, or on a schedule.\n",
                                        [edited]), [])

    def test_the_line_with_a_clause_dropped_is_still_reported_from_windows_and_hits(self):
        patch = PATCH.splitlines()
        hits = ("search for 'HasContactInCurrentStep' in here (literal, exact case): 2 matches in 1 files, 9 files "
                "searched\nhere/sensor.patch:2: " + patch[1].strip() + "\nhere/sensor.patch:9: if (mContactManager.Has")
        self.assertEqual(unfound_quotes(code(CLAIMED), [window("here/sensor.patch", patch, 1, 1),
                                                        window("here/sensor.patch", patch, 2, 3), hits]), [CLAIMED])


# A patch to the cache's notes: one line changed, between two that are not.
NOTES_PATCH = ["@@ -3,4 +3,4 @@", " The cache is cleared only when the person", "-runs clean, or every night.",
               "+runs clean, and never on its own.", " ", " A stale cache is rebuilt in the background."]


class DiffTest(unittest.TestCase):
    """A diff, in what was read or in the answer, is two texts and its own syntax: a quote of either text is found,
    and a diff block's syntax is not a quote."""

    def test_a_diff_blocks_lines_are_compared_without_their_marker_and_its_syntax_is_not_a_quote(self):
        answer = ("The fix, against what was read:\n\n```diff\n"
                  "diff --git a/settings.py b/settings.py\nindex 3f2a1b0..9c8d7e6 100644\n"
                  "--- a/settings.py\n+++ b/settings.py\n"
                  "@@ -12,2 +12,2 @@ def load(path):\n"
                  "-    if not os.path.exists(path):\n+    if not os.path.isfile(path):\n"
                  "         return None\n\\ No newline at end of file\n```\n")
        # what was read is found without its marker; the new line, read nowhere, is reported as the answer has it
        self.assertEqual(unfound_quotes(answer, [READ]), ["+ if not os.path.isfile(path):"])

    def test_a_patch_line_copied_into_a_diff_block_is_found_with_other_space_after_its_marker(self):
        self.assertEqual(unfound_quotes(code("+continue;", "+if (hit.mFraction < 0.0f || hit.mFraction > 1.0f",
                                             tag="diff"), [PATCH]), [])
        self.assertEqual(unfound_quotes(code("+continue;", tag="udiff"), [PATCH]), [])
        self.assertEqual(unfound_quotes(code("+continue;", tag="python"), [PATCH]), ["+continue;"])   # not a diff
        listed ="1. The fix:\n\n   ```patch\n   -    if not os.path.exists(path):\n   ```\n"   # a block in a list item
        self.assertEqual(unfound_quotes(listed, [READ]), [])

    def test_a_passage_of_either_side_of_a_patch_over_a_changed_line_is_found(self):
        new = "> The cache is cleared only when the person runs clean, and never on its own.\n"
        old = 'The old notes said "runs clean, or every night. A stale cache is rebuilt in the background."\n'
        read = window("here/docs/notes.patch", NOTES_PATCH, 1, 6)
        run = "exit 0 after 0.02 s: git diff (in here)\n" + "\n".join(NOTES_PATCH)     # a command's output
        middle = window("here/docs/notes.patch", NOTES_PATCH, 2, 4)                  # no hunk header in it
        for source in (read, run, middle):
            self.assertEqual(unfound_quotes(new, [source]), [])
        for source in (read, run):
            self.assertEqual(unfound_quotes(old, [source]), [])

    def test_a_text_that_is_not_a_patch_keeps_the_lines_that_start_with_a_dash(self):
        notes = window("here/docs/notes.md", ["The cache is cleared only when", "- the person runs clean", "and never "
                                              "on its own."], 1, 3)
        self.assertEqual(unfound_quotes("> The cache is cleared only when and never on its own.\n", [notes]),
                         ["The cache is cleared only when and never on its own."])

    def test_the_line_with_a_clause_dropped_is_still_reported_in_a_diff_block(self):
        self.assertEqual(unfound_quotes(code("+" + CLAIMED, "+    continue;", tag="diff"), [PATCH]), ["+" + CLAIMED])


# The start of two lines of instruction.md as a 27B read it (2026-11-26): Markdown, with emphasis and code spans.
INSTRUCTION = window("here/instruction.md", [
    "**Task description.** A fast dynamic body using `EMotionQuality::LinearCast` can pass through a static sensor in "
    "a single update without notifying the contact listener. Report every static sensor the body really touches on its "
    "way, as an ordinary contact.", "",
    "**Test guidelines.** Build and run the native `UnitTests` target with CMake. Focused tests should call "
    "`PhysicsSystem::Update` and observe the existing `ContactListener` API. From `Build/`, configure a Debug GCC build "
    "with `TARGET_UNIT_TESTS=ON` and the samples disabled."], 1, 3)


class MarkdownTest(unittest.TestCase):
    """Markdown's inline formatting is not text a reader sees: a quote in prose is found with it or without it, on
    either side; a code line is compared with every character."""

    def test_emphasis_and_code_spans_in_what_was_read_are_not_needed_in_a_quote_of_it(self):
        answer = ("> Task description. A fast dynamic body using EMotionQuality::LinearCast can pass through a static "
                  "sensor in a single update\n\n"
                  'It asks that "Focused tests should call PhysicsSystem::Update and observe the existing ContactListener '
                  'API."\n')
        self.assertEqual(unfound_quotes(answer, [INSTRUCTION]), [])

    def test_emphasis_code_spans_and_escapes_the_answer_adds_are_not_compared(self):
        answer = ("> Report every static sensor the body **really** touches on its way, as an *ordinary* contact.\n\n"
                  'It says to "configure a Debug GCC build with TARGET\\_UNIT\\_TESTS=ON and the samples disabled".\n')
        self.assertEqual(unfound_quotes(answer, [INSTRUCTION]), [])

    def test_a_word_changed_is_still_reported_and_a_code_line_keeps_every_character(self):
        answer = ("> Report every static sensor the body touches on its way, as an ordinary contact.\n\n"
                  "> configure a Debug GCC build with TARGETUNITTESTS=ON and the samples disabled\n\n"
                  + code("return a b", "Report every static sensor the body really touches on its way"))
        self.assertEqual(unfound_quotes(answer, [INSTRUCTION, "def f(a, b):\n    return a * b\n"]),
                         ["Report every static sensor the body touches on its way, as an ordinary contact.",
                          "configure a Debug GCC build with TARGETUNITTESTS=ON and the samples disabled",
                          "return a b"])


class NoTextTest(unittest.TestCase):
    """None for a text is no text: no answer has no quotes, and a source that is None, or no sources, is nothing
    read."""

    def test_no_answer_has_no_quotes(self):
        self.assertEqual(unfound_quotes(None, [PATCH]), [])

    def test_a_source_that_is_none_is_nothing_read(self):
        self.assertEqual(unfound_quotes(code(CLAIMED, "continue;"), [None, PATCH, None]), [CLAIMED])
        self.assertEqual(unfound_quotes(code("continue;"), [None]), ["continue;"])

    def test_no_sources_is_nothing_read(self):
        self.assertEqual(unfound_quotes(code("continue;"), None), ["continue;"])


class CraftedTextTest(unittest.TestCase):
    """What was read is the session's untrusted text, up to the 64,000 characters a reply holds: no pattern the
    check runs over it takes time that grows with the square of a line's length. A file of brackets took 4 seconds
    a read for the Markdown link alone (2026-11-26), a first line of brackets and parentheses most of one."""

    QUOTE = '"the cache is cleared only when the person runs clean"'
    N = 64_000

    def assertQuick(self, sources):
        import time
        started = time.perf_counter()
        unfound_quotes(self.QUOTE, sources)
        self.assertLess(time.perf_counter() - started, 0.5)

    def test_a_text_of_link_brackets_is_checked_at_once(self):
        for text in ("[" * (self.N // 2) + "](" * (self.N // 4), "[](" * (self.N // 3), "[[](" * (self.N // 4)):
            with self.subTest(text=text[:8]):
                self.assertQuick([text])

    def test_a_first_line_made_like_a_documents_header_is_checked_at_once(self):
        for head in (" ()" * (self.N // 3), " ():" * (self.N // 4), " (" * (self.N // 2)):
            with self.subTest(head=head[:8]):
                self.assertQuick([head + "\nthe cache is cleared only when the person runs clean"] * 4)

    def test_a_document_named_with_brackets_is_still_its_own_header(self):
        head = "here/my file (1).pdf (pdf, 2 pages): lines 1-2 of 2 of its text, 90 bytes"
        self.assertEqual(unfound_quotes(self.QUOTE, [head + "\nthe cache is cleared only when\nthe person runs clean"]), [])

    def test_a_link_is_still_quoted_by_its_text(self):
        self.assertEqual(unfound_quotes(self.QUOTE, ["[the cache is cleared only when the person runs clean](a.md)"]), [])


if __name__ == "__main__":
    unittest.main()
