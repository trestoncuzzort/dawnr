# AlgoVeri contracts in t

These programs state contracts from [AlgoVeri](https://github.com/haoyuzhao123/algoveri): 77 classical algorithms
with identical functional contracts in Dafny, Verus and Lean. AlgoVeri is licensed under the Apache License 2.0, and
a copy is in `LICENSE-AlgoVeri`. The contracts were read at commit 8e313b0e8110a781009d4b67ca93b3771b5dc9db.

Each `.t` file restates one problem's Dafny contract in t's notation, with a program that meets it:

- Every `requires` and `ensures` appears with the same meaning.
- The preamble's predicates and functions become spec functions.
- [MAPPING.md](MAPPING.md) gives every clause beside its t form and names each departure from the letter of the
  Dafny text, with the reason it keeps the meaning.

Nothing else from AlgoVeri's repository is copied here.

**Why only these.** Of the 77 contracts, 17 use only what t states as written. Five more need only one restatement:
a permutation stated as equal length and equal occurrence counts, an equivalent bounded form of AlgoVeri's
existential over an index permutation. Of those 22, 21 are written here. `k_smallest` is not: its `ensures` is an
existential over a sequence (a sorted permutation whose k-th element is the result), which t's bounded quantifiers
cannot state as written.

The other 55 needed what t did not state on 2026-10-06, and some need more than one of these:

- a quantifier over all sequences: the optimality contracts of the dynamic programs, 7;
- datatypes with fields, such as trees and options: 37;
- heaps, classes or graphs: 23.

Since datatypes carry fields (SPEC.md "Datatypes (v2): fields", 2026-10-07), `discrete_logarithm`, whose result is
an `Option<int>`, is written here too, making 22 programs. Since datatypes may be recursive ("Datatypes (v3):
recursion") and quantifiers may range over a set ("Quantifiers over a collection"), five of the BST family are written
as well, making 27: `bst_search`, `bst_insert`, `bst_zig`, `bst_zigzag`, `bst_zigzig`. Three of the left-leaning
red-black tree's five follow (PREDICT T38), making 30: `llrbt_rotateleft`, `llrbt_rotateright`, `llrbt_flipcolor`,
over one `Tree` whose `Nil` is the source's `None` (MAPPING.md names the departure). Of the other 28 datatype
contracts:
- `linearsys_gf2` needs a quantifier over all sequences;
- `bst_delete`, `splaytree_splay` and `lca` are the BST family's rest, and `llrbt_insert` and `llrbt_delete` the
  red-black tree's;
- tries need a sequence of datatype values, which t's sequences (of ints or of seqs) do not hold;
- the others need segment trees (a map view), ternary search trees or graphs.

`internal/RESEARCH-2026-10-06-landscape.md` gives the counts.

The table of verdicts in all seven kernels is [../ALGOVERI.md](../ALGOVERI.md) (PREDICT T13's read gives what it
shows and what went wrong), produced by:

    python3 t/cli.py verify t/algoveri --jobs 3 --table t/ALGOVERI.md
