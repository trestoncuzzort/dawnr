# A wider reader for the tests: tuples and rows of ints, and the 114 problems it opens; registered before any model is asked

Registered 2026-10-05 05:37Z. "Grow t toward the code people actually write" was taken as a question to measure
before anything was built: which problems can a person not even ask?

## What was measured first (no model involved)

A question reaches `t` only if its tests can be read as `t` values. Of MBPP's 974 problems the pools' reader
(`t/mbpp_dfy.py parse_assertion`, strings and lists of strings) reads 651. The other 323, by the first thing it
refuses in them: a tuple 170, a list whose elements are lists 67, a number that is not whole 47, a dictionary 25,
None 5, other shapes 9. Tuples and nested lists are the two that need no new value: `t` has one sequence type and
`seq<seq>`, and an MBPP tuple is, most of the time, a list that happens to be written with round brackets.

## The change

Two options of the reader, both off by default so that no pool to v5, no split and no panel moves:

- `tuples`: a tuple is read as the list of the same elements, at any depth;
- `nested_ints`: a list every element of which is a list of ints is read as `seq<seq>`, the representation a list of
  strings already has.

Still refused, by name: a tuple or list that mixes kinds of element (`('fox', 16, 19)`), a float, a dictionary,
None, three levels of nesting. With both options the reader reads **796 of the 974 (82%, from 67%)**: 145 problems
no pool held, none of them in the split, so no model here has been trained on or measured against one.

- **For a person asking** (`t/answer.py entry_of`, so `dawnr ask`, `dawnr spec`): tests with tuples and rows are
  read, and what still cannot be read is said in words ("the expected value is a number that is not whole (t has
  integers only)"). The Python handed back (`t/to_python.py`) writes its result as the tests write theirs, a tuple
  where they have a tuple, at each depth, or Python's `==` would fail the question's own test.
- **Pool v7** (`t/spec_experiment.py wider_pool`): pool v5 plus those 145, under pool v3's other gates unchanged.
- **The wider panel.** The 145 were audited against the published model's rows before anything else
  (`t/heldout_audit.py`, the lineage and twin readings): 31 are matched (10 by MBPP-DFY's own formalisation, 28 by a
  program that behaves as the reference does) and never enter; **114** are a held-out panel from their first day
  (`t/decontamination-wider-2026-10-05.json`, `heldout_audit.wider_clean()`). A row build is checked against them
  like the other panels; the round-4 rows match none.

## Predictions (the round-4 student's three seeds, `PREDICT-2026-10-05-teacher4-student.md`; the shipped route under pool v7, the scoreboard's instrument)

- **W1.** The seeds' mean on the wider 114 is at least 5 proved by at least one prover, with a complete,
  reference-checked specification.
- **W2.** The mean by all seven is at least 2, and lower as a share than on the clean 182: nested sequences are
  where Frama-C and the proof assistants abstain most.
- **W3.** At least one problem whose tests pass a tuple of ints is proved by some seed.

- **W4, what a person gets today.** The published model, as installed (Q8_0, llama-server on a CPU), through the
  gate `dawnr ask` runs (`t/answer.py`: five answers, an independent Python solution, five more for consistency, the
  provers), asked each of the 114 with the problem's own words and tests and nothing else: it shows an answer for at
  least 5 of them, and at least 70% of the answers it shows agree with the problem's reference on drawn inputs with a
  complete specification (`~/scratch/wider/ask_batch.py`; the reference is read only afterwards, to score).

No seed's result on this panel gates anything. The comparison that would say what fine-tuning adds here (the
untrained 4B and Phi-4-mini with 17 answers on the same 114) is its own registration when a card is free.

## What it does not do

It adds no type. Of the 178 problems still unread, 61 stop at a number that is not whole, 61 at a tuple or list
that mixes kinds or nests three deep, 34 at a dictionary, 7 at None. Those are the next three: a record or mixed pair at the boundary, a finite map,
and a decision about reals that seven provers can share. Each is a change to the language and to every lowering, with
its own registration; the reader was the part that cost no kernel anything.

## Amendment, 2026-10-05 05:52Z, before any answer on the panel had been read: the panel is 111

A check the first audit lacked: is the reader's reading faithful to the problem? Each problem's own reference was
called with the reader's reading of its tests and compared with the reader's reading of the expected values. All 182
of the clean 182 reproduce. Of the wider 145, four do not: 143 (already matched by a row), 222 and 398 (a one-letter
string among numbers is read as a character, as `t` reads every one-letter string, and that changes what the tuple
holds), and 712 (its tests have two shapes). The instrument cannot ask those questions, so they are in no panel:
**the wider panel is 111** (`unfaithful_ids` in `t/decontamination-wider-2026-10-05.json`), and W1 to W4 are read
on the 111. The W4 batch had started on the 114 at 05:46Z and none of its answers had been opened; the three are
generated and left out of every count.
