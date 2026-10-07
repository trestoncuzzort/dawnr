datatype Tree = Leaf | Node(v: int, l: Tree, r: Tree)
t 1
gate recursion
task tree_sum(tr: Tree) returns (s: int)
  ensures s == total(tr)
  decreases tr
spec fun total(q: Tree): int
  decreases q
= case q { Leaf => 0, Node(v, l, r) => v + total(l) + total(r) }
{
  s := case tr { Leaf => 0, Node(v, l, r) => v + tree_sum(l) + tree_sum(r) };
}
