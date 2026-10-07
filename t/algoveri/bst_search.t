datatype Tree = Empty | Node(val: int, left: Tree, right: Tree)
t 1
gate recursion
task search(tree: Tree, v: int) returns (res: bool)
  requires v >= 0
  requires is_bst(tree)
  ensures res == (v in view(tree))
  decreases tree
spec fun view(tree: Tree): set
  decreases tree
= case tree { Empty => {}, Node(val, left, right) => union(union(view(left), view(right)), {val}) }
spec fun is_bst(tree: Tree): bool
  decreases tree
= case tree { Empty => true, Node(val, left, right) => (forall x in view(left) . x < val) and is_bst(left) and (forall x in view(right) . x > val) and is_bst(right) }
lemma bst_split(val: int, left: Tree, right: Tree, v: int)
  requires is_bst(Tree.Node(val, left, right))
  ensures v < val ==> ((v in view(Tree.Node(val, left, right))) == (v in view(left)))
  ensures v > val ==> ((v in view(Tree.Node(val, left, right))) == (v in view(right)))
{
  assert view(Tree.Node(val, left, right)) == union(union(view(left), view(right)), {val});
  assert forall x in view(left) . x < val;
  assert forall x in view(right) . x > val;
}
{
  if case tree { Empty => false, Node(val, left, right) => true } {
    bst_split(tree.val, tree.left, tree.right, v);
  }
  res := case tree { Empty => false, Node(val, left, right) => if v == val then true else if v < val then search(left, v) else search(right, v) };
}
