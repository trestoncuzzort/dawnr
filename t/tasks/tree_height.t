datatype Tree = Leaf | Node(v: int, l: Tree, r: Tree)
t 1
gate recursion
task tree_height(tr: Tree) returns (h: int)
  ensures h == height(tr)
  ensures h >= 0
  decreases tr
spec fun height(q: Tree): int
  decreases q
= case q { Leaf => 0, Node(v, l, r) => 1 + max(height(l), height(r)) }
{
  h := case tr { Leaf => 0, Node(v, l, r) => 1 + max(tree_height(l), tree_height(r)) };
}
