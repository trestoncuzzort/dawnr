datatype Tree = Nil | Node(val: int, is_red: bool, left: Tree, right: Tree)
t 1
task rotate_right(node: Tree) returns (res: Tree)
  requires case node { Nil => false, Node(val, is_red, left, right) => true }
  requires is_bst(node)
  requires case node.left { Nil => false, Node(val, is_red, left, right) => is_red }
  ensures case res { Nil => false, Node(val, is_red, left, right) => true }
  ensures case res.right { Nil => false, Node(val, is_red, left, right) => true }
  ensures is_bst(res)
  ensures view(res) == view(node)
  ensures black_height(res) == black_height(node)
  ensures res.is_red == node.is_red
  ensures res.right.is_red
spec fun view(tree: Tree): set
  decreases tree
= case tree { Nil => {}, Node(val, is_red, left, right) => union(union(view(left), view(right)), {val}) }
spec fun is_bst(tree: Tree): bool
  decreases tree
= case tree { Nil => true, Node(val, is_red, left, right) => (forall x in view(left) . x < val) and is_bst(left) and (forall x in view(right) . x > val) and is_bst(right) }
spec fun black_height(tree: Tree): int
  decreases tree
= case tree { Nil => 1, Node(val, is_red, left, right) => if black_height(left) != -1 and black_height(right) != -1 and black_height(left) == black_height(right) then (if not is_red then black_height(left) + 1 else black_height(left)) else -1 }
lemma rotate_right_keeps_order(v: int, c: bool, lv: int, lc: bool, ll: Tree, lr: Tree, r: Tree)
  requires is_bst(Tree.Node(v, c, Tree.Node(lv, lc, ll, lr), r))
  ensures is_bst(Tree.Node(lv, c, ll, Tree.Node(v, true, lr, r)))
  ensures view(Tree.Node(lv, c, ll, Tree.Node(v, true, lr, r))) == view(Tree.Node(v, c, Tree.Node(lv, lc, ll, lr), r))
{
  assert lv in view(Tree.Node(lv, lc, ll, lr));
  assert lv < v;
  assert forall x in view(lr) . x in view(Tree.Node(lv, lc, ll, lr));
  assert forall x in view(lr) . x > lv and x < v;
  assert forall x in view(r) . x > v;
  assert is_bst(Tree.Node(v, true, lr, r));
  assert view(Tree.Node(v, true, lr, r)) == union(union(view(lr), view(r)), {v});
  assert forall x in view(Tree.Node(v, true, lr, r)) . x > lv;
}
{
  rotate_right_keeps_order(node.val, node.is_red, node.left.val, node.left.is_red, node.left.left, node.left.right, node.right);
  res := case node { Nil => node, Node(v, c, l, r) => case l { Nil => node, Node(lv, lc, ll, lr) => Tree.Node(lv, c, ll, Tree.Node(v, true, lr, r)) } };
}
