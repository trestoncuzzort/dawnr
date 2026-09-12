# lean: closing the composed seq goals

Design written 2026-09-12 from lower_lean.py's notes (THE FRAME-FACT GAP,
the composed get-lemmas of waves H and I, the per-site script that closed
swapFirstAndLast in wave J, the append-of-slices probe of wave K). Rows:
dafny_synthesis 106 appendArrayToSeq, 240 replaceLastElement, 586
splitAndAppend, then 470 pairwiseAddition, 578 interleave, 603
lucidNumbers, 610 removeElement, 576 isSublist.

## The shape of a per-site script, in three steps

1. **Lengths first.** Before any case split, rewrite every length term
   the goal or a hypothesis mentions into omega's normal form:
   `List.length_append`, `List.length_take`, `List.length_drop`,
   `List.length_set`, `List.length_replicate`, then `Nat.min_def` on the
   `min` that `take` leaves, and split that `min` at once (`split` on the
   `if` it produces, in hypotheses too: `simp only [...] at *` then
   `split_ifs at *`). The wave K probe stopped on an `ite` inside a
   hypothesis that `repeat' split` never reached; `split_ifs at *` reaches
   it. After this step every length is a linear expression and omega can
   discharge every side condition the get-lemmas ask for.
2. **One get-lemma per composed term, unconditional.** For each composed
   term in the goal (`(a ++ b)[i]`, `(l.take n ++ l.drop n)[i]`,
   `(l.set i x).set j y`), cite the matching bridge lemma with the index
   case chosen by the linear facts from step 1 (`List.getElem_append_left`
   with `hi : i < a.length`, else `_right`), never the ite-conclusion form
   grind cannot split. The three ite-free corollaries of wave I are the
   right shape; extend them to `append` over `take`/`drop` (the rotate
   shape of 586) and to a `set` under an `append` (106's loop body).
3. **Close.** `simp only [the cited facts] ; omega` or `decide` for a
   ground index; `exact` the rewritten equality.

## The loop-preservation obligation of 106

`r := r ++ [a[i]]` under an invariant `forall k < i, r[k] = f(a[k])`:
the script introduces `k` and `hk : k < i + 1`, splits `k < r.length`
(the old prefix, cite the invariant at `k` with `List.getElem_append_left`)
from `k = r.length` (the new cell, `List.getElem_append_right` plus
`List.getElem_singleton`), and closes each with `simp only` and `omega`.
Generate it from the shape (an append of a singleton inside a loop body
whose invariant is a forall over the prefix), never per task.

## The timeouts

470, 578, 603: read what grind spends heartbeats on (`set_option
trace.grind.ematch true` on the generated file in a scratch run); the
usual cause is a quantified invariant with no trigger term that the
bridge lemmas match, fixed by citing the specific instance (step 2)
instead of leaving it to e-matching. 610: two sequential loops, chain
the loop functions as lower_fstar.py's gen_loop_chain does. 576: the
same slice equality that dafny needed a trigger for; cite the slice
get-lemma at the witness index.
