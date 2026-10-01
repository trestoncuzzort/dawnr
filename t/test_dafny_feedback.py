"""Dafny's own diagnostics as the repair message (arXiv:2410.15756 3.3). The parser, on real output."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dafny_feedback as df                                     # noqa: E402

SOURCE = """method F(n: int) returns (r: int)
  requires (n >= 2)
  ensures (r >= 1)
  ensures ((n >= 5) ==> (r > n))
{
  var i: int := 5;
  r := 1;
  while (i <= n)
    invariant (r >= 1)
    invariant ((i >= 5) && (i <= (n + 1)))
    decreases ((n - i) + 1)
  {
    r := (r + i);
    i := (i + 1);
  }
}"""
# dafny 4.11's text for a failed postcondition and a failed invariant (shape measured on the lab, 2026-10-01)
OUTPUT = """task.dfy(5,0): Error: a postcondition could not be proved on this return path
  |
5 | {
  | ^

task.dfy(4,27): Related location: this is the postcondition that could not be proved
  |
4 |   ensures ((n >= 5) ==> (r > n))
  |                            ^

task.dfy(10,14): Error: this loop invariant could not be proved on entry
 Related message: loop invariant violation
   |
10 |     invariant ((i >= 5) && (i <= (n + 1)))
   |               ^

Dafny program verifier finished with 0 verified, 2 errors
"""


def test_each_error_becomes_one_line_quoting_its_clause():
    assert df.parse(OUTPUT, SOURCE) == [
        "- a postcondition could not be proved on this return path: `ensures ((n >= 5) ==> (r > n))`",
        "- this loop invariant could not be proved on entry: `invariant ((i >= 5) && (i <= (n + 1)))`"]


def test_the_same_error_twice_is_said_once_and_the_list_is_capped():
    twice = OUTPUT + OUTPUT
    assert len(df.parse(twice, SOURCE)) == 2
    many = "".join(f"task.dfy({k},1): Error: e{k}\n" for k in range(1, 12))
    assert len(df.parse(many, SOURCE)) == df.MAX_LINES


def test_running_out_of_resources_is_reported_and_silence_is_empty():
    assert df.parse("Verification out of resource (F)\n", SOURCE) == [
        "- Dafny ran out of its resource limit before it could decide"]
    assert df.parse("Dafny program verifier finished with 2 verified, 0 errors\n", SOURCE) == []


def test_the_message_is_the_head_and_the_lines():
    said = df.parse(OUTPUT, SOURCE)
    assert df.message(said).startswith(df.HEAD) and df.message(said).endswith(said[-1])


def test_a_row_that_is_not_a_proof_failure_is_returned_as_it_was():
    row = {"failure": "parse", "prompt": [{"role": "user", "content": "x"}]}
    assert df.with_dafny(row) is row
