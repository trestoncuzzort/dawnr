datatype Tree = Leaf | Node(v: int, l: Tree, r: Tree)
t 1
gate recursion
task tree_insert(tr: Tree, x: int) returns (m: Tree)
  ensures in_tree(m, x)
  ensures size(m) == size(tr) + 1
  decreases tr
spec fun in_tree(q: Tree, y: int): bool
  decreases q
= case q { Leaf => false, Node(v, l, r) => v == y or in_tree(l, y) or in_tree(r, y) }
spec fun size(q: Tree): int
  decreases q
= case q { Leaf => 0, Node(v, l, r) => 1 + size(l) + size(r) }
{
  m := case tr { Leaf => Tree.Node(x, Tree.Leaf, Tree.Leaf), Node(v, l, r) => if x < v then Tree.Node(v, tree_insert(l, x), r) else Tree.Node(v, l, tree_insert(r, x)) };
}
