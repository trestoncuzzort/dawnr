datatype Tree = Leaf | Node(v: int, l: Tree, r: Tree)
t 1
gate recursion
task tree_mirror(tr: Tree) returns (m: Tree)
  ensures m == mirror(tr)
  decreases tr
spec fun mirror(q: Tree): Tree
  decreases q
= case q { Leaf => Tree.Leaf, Node(v, l, r) => Tree.Node(v, mirror(r), mirror(l)) }
{
  m := case tr { Leaf => Tree.Leaf, Node(v, l, r) => Tree.Node(v, tree_mirror(r), tree_mirror(l)) };
}
