datatype Tree = Empty | Node(val: int, left: Tree, right: Tree)
t 1
task zig_zag(g: Tree) returns (res: Tree)
  requires case g { Empty => false, Node(val, left, right) => true }
  requires case g.left { Empty => false, Node(val, left, right) => true }
  requires case g.left.right { Empty => false, Node(val, left, right) => true }
  requires is_bst(g)
  ensures is_bst(res)
  ensures view(res) == view(g)
  ensures res.val == g.left.right.val
spec fun view(tree: Tree): set
  decreases tree
= case tree { Empty => {}, Node(val, left, right) => union(union(view(left), view(right)), {val}) }
spec fun is_bst(tree: Tree): bool
  decreases tree
= case tree { Empty => true, Node(val, left, right) => (forall x in view(left) . x < val) and is_bst(left) and (forall x in view(right) . x > val) and is_bst(right) }
lemma zz_inner(gv: int, pv: int, xv: int, a: Tree, b: Tree, c: Tree, d: Tree)
  requires is_bst(Tree.Node(gv, Tree.Node(pv, a, Tree.Node(xv, b, c)), d))
  ensures is_bst(Tree.Node(pv, a, Tree.Node(xv, b, c))) and is_bst(d)
  ensures forall x in view(Tree.Node(pv, a, Tree.Node(xv, b, c))) . x < gv
  ensures forall x in view(d) . x > gv
{
}
lemma zz_parts(gv: int, pv: int, xv: int, a: Tree, b: Tree, c: Tree, d: Tree)
  requires is_bst(Tree.Node(pv, a, Tree.Node(xv, b, c))) and is_bst(d)
  requires forall x in view(Tree.Node(pv, a, Tree.Node(xv, b, c))) . x < gv
  requires forall x in view(d) . x > gv
  ensures pv < xv and xv < gv
  ensures is_bst(a) and is_bst(b) and is_bst(c) and is_bst(d)
  ensures forall x in view(a) . x < pv
  ensures forall x in view(b) . x > pv and x < xv
  ensures forall x in view(c) . x > xv and x < gv
  ensures forall x in view(d) . x > gv
{
  assert is_bst(Tree.Node(xv, b, c));
  assert xv in view(Tree.Node(xv, b, c));
  assert xv in view(Tree.Node(pv, a, Tree.Node(xv, b, c)));
  assert pv in view(Tree.Node(pv, a, Tree.Node(xv, b, c)));
  assert forall x in view(b) . x in view(Tree.Node(xv, b, c));
  assert forall x in view(c) . x in view(Tree.Node(xv, b, c));
  assert forall x in view(c) . x in view(Tree.Node(pv, a, Tree.Node(xv, b, c)));
}
lemma zz_order(gv: int, pv: int, xv: int, a: Tree, b: Tree, c: Tree, d: Tree)
  requires pv < xv and xv < gv
  requires is_bst(a) and is_bst(b) and is_bst(c) and is_bst(d)
  requires forall x in view(a) . x < pv
  requires forall x in view(b) . x > pv and x < xv
  requires forall x in view(c) . x > xv and x < gv
  requires forall x in view(d) . x > gv
  ensures is_bst(Tree.Node(xv, Tree.Node(pv, a, b), Tree.Node(gv, c, d)))
{
  assert is_bst(Tree.Node(pv, a, b));
  assert is_bst(Tree.Node(gv, c, d));
  assert forall x in view(Tree.Node(pv, a, b)) . x < xv;
  assert forall x in view(Tree.Node(gv, c, d)) . x > xv;
}
lemma zz_view(gv: int, pv: int, xv: int, a: Tree, b: Tree, c: Tree, d: Tree)
  ensures view(Tree.Node(xv, Tree.Node(pv, a, b), Tree.Node(gv, c, d))) == view(Tree.Node(gv, Tree.Node(pv, a, Tree.Node(xv, b, c)), d))
{
  assert view(Tree.Node(pv, a, b)) == union(union(view(a), view(b)), {pv});
  assert view(Tree.Node(gv, c, d)) == union(union(view(c), view(d)), {gv});
  assert view(Tree.Node(xv, b, c)) == union(union(view(b), view(c)), {xv});
  assert view(Tree.Node(pv, a, Tree.Node(xv, b, c))) == union(union(view(a), view(Tree.Node(xv, b, c))), {pv});
}
{
  zz_inner(g.val, g.left.val, g.left.right.val, g.left.left, g.left.right.left, g.left.right.right, g.right);
  zz_parts(g.val, g.left.val, g.left.right.val, g.left.left, g.left.right.left, g.left.right.right, g.right);
  zz_order(g.val, g.left.val, g.left.right.val, g.left.left, g.left.right.left, g.left.right.right, g.right);
  zz_view(g.val, g.left.val, g.left.right.val, g.left.left, g.left.right.left, g.left.right.right, g.right);
  res := case g { Empty => g, Node(gv, p, d) => case p { Empty => g, Node(pv, a, x) => case x { Empty => g, Node(xv, b, c) => Tree.Node(xv, Tree.Node(pv, a, b), Tree.Node(gv, c, d)) } } };
}
