datatype Tree = Nil | Node(val: int, is_red: bool, left: Tree, right: Tree)
t 1
task rotate_left(node: Tree) returns (res: Tree)
  requires case node { Nil => false, Node(val, is_red, left, right) => true }
  requires is_bst(node)
  requires case node.right { Nil => false, Node(val, is_red, left, right) => is_red }
  ensures case res { Nil => false, Node(val, is_red, left, right) => true }
  ensures case res.left { Nil => false, Node(val, is_red, left, right) => true }
  ensures is_bst(res)
  ensures view(res) == view(node)
  ensures black_height(res) == black_height(node)
  ensures res.is_red == node.is_red
  ensures res.left.is_red
spec fun view(tree: Tree): set
  decreases tree
= case tree { Nil => {}, Node(val, is_red, left, right) => union(union(view(left), view(right)), {val}) }
spec fun is_bst(tree: Tree): bool
  decreases tree
= case tree { Nil => true, Node(val, is_red, left, right) => (forall x in view(left) . x < val) and is_bst(left) and (forall x in view(right) . x > val) and is_bst(right) }
spec fun black_height(tree: Tree): int
  decreases tree
= case tree { Nil => 1, Node(val, is_red, left, right) => if black_height(left) != -1 and black_height(right) != -1 and black_height(left) == black_height(right) then (if not is_red then black_height(left) + 1 else black_height(left)) else -1 }
lemma rotate_left_keeps_order(v: int, c: bool, l: Tree, rv: int, rc: bool, rl: Tree, rr: Tree)
  requires is_bst(Tree.Node(v, c, l, Tree.Node(rv, rc, rl, rr)))
  ensures is_bst(Tree.Node(rv, c, Tree.Node(v, true, l, rl), rr))
  ensures view(Tree.Node(rv, c, Tree.Node(v, true, l, rl), rr)) == view(Tree.Node(v, c, l, Tree.Node(rv, rc, rl, rr)))
{
  assert rv in view(Tree.Node(rv, rc, rl, rr));
  assert rv > v;
  assert forall x in view(rl) . x in view(Tree.Node(rv, rc, rl, rr));
  assert forall x in view(rl) . x > v and x < rv;
  assert forall x in view(l) . x < v;
  assert is_bst(Tree.Node(v, true, l, rl));
  assert view(Tree.Node(v, true, l, rl)) == union(union(view(l), view(rl)), {v});
  assert forall x in view(Tree.Node(v, true, l, rl)) . x < rv;
}
{
  rotate_left_keeps_order(node.val, node.is_red, node.left, node.right.val, node.right.is_red, node.right.left, node.right.right);
  res := case node { Nil => node, Node(v, c, l, r) => case r { Nil => node, Node(rv, rc, rl, rr) => Tree.Node(rv, c, Tree.Node(v, true, l, rl), rr) } };
}
