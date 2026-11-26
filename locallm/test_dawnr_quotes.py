"""test_dawnr_quotes.py: dawnr_agent/quotes.py, the quotes in an answer that are in nothing the session read.

What must hold: a code line that drops a clause from the line it stands for is reported, and a line copied exactly
is not, whether it was read in a patch (with its "+" or without), an fs_read window (with its line numbers or
without) or an fs_search hit; a code line is looked for one source line at a time, a blockquote line and a passage
of six words or more in double quotes across the source's line breaks too; a passage of fewer than six words, and a
line with nothing to check in it (punctuation, an ellipsis, fewer than four characters), is never reported; what is
reported comes in the order of the answer, once each. Standard library only.
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


if __name__ == "__main__":
    unittest.main()
