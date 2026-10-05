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

## Amendment, 2026-10-05 05:51Z, before any answer on the panel had been read: the panel is 111

A check the first audit lacked: is the reader's reading faithful to the problem? Each problem's own reference was
called with the reader's reading of its tests and compared with the reader's reading of the expected values. All 182
of the clean 182 reproduce. Of the wider 145, four do not: 143 (already matched by a row), 222 and 398 (a one-letter
string among numbers is read as a character, as `t` reads every one-letter string, and that changes what the tuple
holds), and 712 (its tests have two shapes). The instrument cannot ask those questions, so they are in no panel:
**the wider panel is 111** (`unfaithful_ids` in `t/decontamination-wider-2026-10-05.json`), and W1 to W4 are read
on the 111. The W4 batch had started on the 114 at 05:46Z and none of its answers had been opened; the three are
generated and left out of every count.

## W5, registered 2026-10-05 05:59Z, before the larger model is asked anything: what a person with a 24 GB card could get

The scoreboard says the prompted Qwen3.5-27B proves 33 of the clean 182 where the published 4B proves 18, with 17
answers a problem, at fp8 on a 48 GB card and with all seven provers. Whether that helps a person depends on three
things nobody has measured: 4 bits instead of fp8 (unsloth's `Qwen3.5-27B-Q4_K_M.gguf`, 16.7 GB, Apache-2.0, which
fits a 24 GB card with an 8k context), the gate `dawnr ask` runs instead of 17 pooled answers, and Dafny alone.

Same panel, same gate, same conditions as W4, one thing changed: the model. llama.cpp's CUDA build serves the 27B at
Q4_K_M with an 8,192-token context on one of the lab's cards (beside a training run; the card has the room); it
answers both roles, the `t` answer under prompt v5 (the language described with examples, because it was never
trained on `t`) and the Python beside it; `t/answer.py` with five answers and consistency 5, Dafny only, on the
wider 111.

- **W5.** It shows an answer for at least 12 of the 111, at least twice what the published model shows in W4, and
  at least 70% of the answers it shows agree with the reference on drawn inputs with a complete specification.

If W5 holds, the mode is worth building into `dawnr` for people with such a card (an installer option, one server
for both roles); if it does not, the larger model's lead on the scoreboard does not survive the trip to a consumer
card and the installer stays as it is. Either way the result is the 4-bit model's, through this gate; it says
nothing new about fp8 with seven provers.

## Outcome of W4 and W5, 2026-10-05 11:33Z

Both batches asked all 111 (`~/scratch/wider/score.py`; the reference was read only to score).

| | asked | shown | of those, agree with the reference with a complete specification | Python handed back | median time a question |
|---|---|---|---|---|---|
| W4: the published model (4B, Q8_0, the desktop's CPU) | 111 | 12 | 11 | 11 | 157 s |
| W5: Qwen3.5-27B prompted (Q4_K_M, a lab card, the desktop's Dafny) | 111 | 16 | 15 | 15 | 143 s |

- **W4: holds.** 12 shown (the bar was 5) and 11 of 12 agree (92%; the bar was 70%).
- **W5: fails on one clause.** 16 shown (the bar of 12 is met) and 15 of 16 agree (94%), but 16 is not twice 12.
  By the rule above the installer stays as it is: at four bits, through this gate and with Dafny alone, six times
  the parameters buy four more answers in 111.

**The one answer in each batch that does not agree is the same problem, and the reference is the odd one.**
Problem 889 asks for "a function to reverse each list in a given list of lists". Both models' shown programs
reverse each list and prove it. The benchmark's reference sorts each list in descending order, which is the same
thing only on the tests' already ascending rows. It is counted as a miss in the table because the scorer is the
registered one; `dawnr verify`, given that reference as the function and those words as its docstring, refuses it
and says why (`t/PREDICT-2026-10-05-verify-python.md`, outcome).

**The gate has changed since these batches began.** Both started before specifications were also held to inputs
larger than the examples (`t/LARGER-INPUTS-2026-10-05.md`). Re-judged with the gate as it stands, from what each
run recorded and without asking a model again, one shown answer in each is no longer shown (problem 196, the
specification says too little about larger inputs): **11 for the published model and 15 for the 27B.** No answer
that agrees with its reference under the larger reading is lost.

**Where the refused questions stop** (each question counted once, at the furthest stage any of its answers reached):

| | no answer parses, is well formed and passes the tests | a test-passing answer, no specification that could be supported | a supported specification, no proof | read more than one way | shown |
|---|---|---|---|---|---|
| W4, published 4B | 77 | 13 | 7 | 2 | 12 |
| W5, prompted 27B | 54 | 30 | 9 | 2 | 16 |

For the published model the wall is the first column: 77 of 99 refused questions never get a program that runs
its own tests (of its refused answers 185 do not parse, 122 are not well formed, 125 fail a test). The 27B, which
has never been trained on `t`, gets past that more often (267 of its answers still do not parse) and then stops
at the specification: 30 questions have a test-passing program and no specification the gate could support.
An exploratory run on the dev panel the same day (`~/scratch/measure/diag_parse.py`, not registered) held the
published model's decoding to `t`'s grammar: unparseable answers fell from 31 to 12 of 120 and the problems with a
test-passing answer stayed at 7 of 40, so for the trained model parsing is a symptom and not the lever.

