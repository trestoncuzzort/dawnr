datatype Tree = Empty | Node(val: int, left: Tree, right: Tree)
t 1
task zig(tree: Tree) returns (res: Tree)
  requires case tree { Empty => false, Node(val, left, right) => true }
  requires case tree.left { Empty => false, Node(val, left, right) => true }
  requires is_bst(tree)
  ensures is_bst(res)
  ensures view(res) == view(tree)
  ensures res.val == tree.left.val
  ensures (case res.right { Empty => false, Node(val, left, right) => true }) and res.right.val == tree.val
spec fun view(tree: Tree): set
  decreases tree
= case tree { Empty => {}, Node(val, left, right) => union(union(view(left), view(right)), {val}) }
spec fun is_bst(tree: Tree): bool
  decreases tree
= case tree { Empty => true, Node(val, left, right) => (forall x in view(left) . x < val) and is_bst(left) and (forall x in view(right) . x > val) and is_bst(right) }
lemma zig_keeps_order(val: int, lv: int, ll: Tree, lr: Tree, right: Tree)
  requires is_bst(Tree.Node(val, Tree.Node(lv, ll, lr), right))
  ensures is_bst(Tree.Node(lv, ll, Tree.Node(val, lr, right)))
  ensures view(Tree.Node(lv, ll, Tree.Node(val, lr, right))) == view(Tree.Node(val, Tree.Node(lv, ll, lr), right))
{
  assert lv in view(Tree.Node(lv, ll, lr));
  assert lv < val;
  assert forall x in view(lr) . x in view(Tree.Node(lv, ll, lr));
  assert forall x in view(lr) . x > lv and x < val;
  assert forall x in view(right) . x > val;
  assert is_bst(Tree.Node(val, lr, right));
  assert view(Tree.Node(val, lr, right)) == union(union(view(lr), view(right)), {val});
  assert forall x in view(Tree.Node(val, lr, right)) . x > lv;
}
{
  zig_keeps_order(tree.val, tree.left.val, tree.left.left, tree.left.right, tree.right);
  res := case tree { Empty => tree, Node(val, left, right) => case left { Empty => tree, Node(lv, ll, lr) => Tree.Node(lv, ll, Tree.Node(val, lr, right)) } };
}
