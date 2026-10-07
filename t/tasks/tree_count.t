datatype Tree = Leaf | Node(v: int, l: Tree, r: Tree)
t 1
gate recursion
task tree_count(tr: Tree, x: int) returns (c: int)
  ensures c == occ(tr, x)
  ensures c >= 0
  decreases tr
spec fun occ(q: Tree, y: int): int
  decreases q
= case q { Leaf => 0, Node(v, l, r) => (if v == y then 1 else 0) + occ(l, y) + occ(r, y) }
{
  c := case tr { Leaf => 0, Node(v, l, r) => (if v == x then 1 else 0) + tree_count(l, x) + tree_count(r, x) };
}
