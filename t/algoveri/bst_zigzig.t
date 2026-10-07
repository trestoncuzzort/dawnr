datatype Tree = Empty | Node(val: int, left: Tree, right: Tree)
t 1
task zig_zig(g: Tree) returns (res: Tree)
  requires case g { Empty => false, Node(val, left, right) => true }
  requires case g.left { Empty => false, Node(val, left, right) => true }
  requires case g.left.left { Empty => false, Node(val, left, right) => true }
  requires is_bst(g)
  ensures is_bst(res)
  ensures view(res) == view(g)
  ensures res.val == g.left.left.val
spec fun view(tree: Tree): set
  decreases tree
= case tree { Empty => {}, Node(val, left, right) => union(union(view(left), view(right)), {val}) }
spec fun is_bst(tree: Tree): bool
  decreases tree
= case tree { Empty => true, Node(val, left, right) => (forall x in view(left) . x < val) and is_bst(left) and (forall x in view(right) . x > val) and is_bst(right) }
lemma zzz_inner(gv: int, pv: int, xv: int, a: Tree, b: Tree, c: Tree, d: Tree)
  requires is_bst(Tree.Node(gv, Tree.Node(pv, Tree.Node(xv, a, b), c), d))
  ensures is_bst(Tree.Node(pv, Tree.Node(xv, a, b), c)) and is_bst(d)
  ensures forall x in view(Tree.Node(pv, Tree.Node(xv, a, b), c)) . x < gv
  ensures forall x in view(d) . x > gv
{
}
lemma zzz_parts(gv: int, pv: int, xv: int, a: Tree, b: Tree, c: Tree, d: Tree)
  requires is_bst(Tree.Node(pv, Tree.Node(xv, a, b), c)) and is_bst(d)
  requires forall x in view(Tree.Node(pv, Tree.Node(xv, a, b), c)) . x < gv
  requires forall x in view(d) . x > gv
  ensures xv < pv and pv < gv
  ensures is_bst(a) and is_bst(b) and is_bst(c) and is_bst(d)
  ensures forall x in view(a) . x < xv
  ensures forall x in view(b) . x > xv and x < pv
  ensures forall x in view(c) . x > pv and x < gv
  ensures forall x in view(d) . x > gv
{
  assert is_bst(Tree.Node(xv, a, b));
  assert xv in view(Tree.Node(xv, a, b));
  assert xv in view(Tree.Node(pv, Tree.Node(xv, a, b), c));
  assert pv in view(Tree.Node(pv, Tree.Node(xv, a, b), c));
  assert forall x in view(a) . x in view(Tree.Node(xv, a, b));
  assert forall x in view(b) . x in view(Tree.Node(xv, a, b));
  assert forall x in view(c) . x in view(Tree.Node(pv, Tree.Node(xv, a, b), c));
}
lemma zzz_order(gv: int, pv: int, xv: int, a: Tree, b: Tree, c: Tree, d: Tree)
  requires xv < pv and pv < gv
  requires is_bst(a) and is_bst(b) and is_bst(c) and is_bst(d)
  requires forall x in view(a) . x < xv
  requires forall x in view(b) . x > xv and x < pv
  requires forall x in view(c) . x > pv and x < gv
  requires forall x in view(d) . x > gv
  ensures is_bst(Tree.Node(xv, a, Tree.Node(pv, b, Tree.Node(gv, c, d))))
{
  assert is_bst(Tree.Node(gv, c, d));
  assert forall x in view(Tree.Node(gv, c, d)) . x > pv;
  assert is_bst(Tree.Node(pv, b, Tree.Node(gv, c, d)));
  assert forall x in view(Tree.Node(pv, b, Tree.Node(gv, c, d))) . x > xv;
}
lemma zzz_view(gv: int, pv: int, xv: int, a: Tree, b: Tree, c: Tree, d: Tree)
  ensures view(Tree.Node(xv, a, Tree.Node(pv, b, Tree.Node(gv, c, d)))) == view(Tree.Node(gv, Tree.Node(pv, Tree.Node(xv, a, b), c), d))
{
  assert view(Tree.Node(gv, c, d)) == union(union(view(c), view(d)), {gv});
  assert view(Tree.Node(pv, b, Tree.Node(gv, c, d))) == union(union(view(b), view(Tree.Node(gv, c, d))), {pv});
  assert view(Tree.Node(xv, a, b)) == union(union(view(a), view(b)), {xv});
  assert view(Tree.Node(pv, Tree.Node(xv, a, b), c)) == union(union(view(Tree.Node(xv, a, b)), view(c)), {pv});
}
{
  zzz_inner(g.val, g.left.val, g.left.left.val, g.left.left.left, g.left.left.right, g.left.right, g.right);
  zzz_parts(g.val, g.left.val, g.left.left.val, g.left.left.left, g.left.left.right, g.left.right, g.right);
  zzz_order(g.val, g.left.val, g.left.left.val, g.left.left.left, g.left.left.right, g.left.right, g.right);
  zzz_view(g.val, g.left.val, g.left.left.val, g.left.left.left, g.left.left.right, g.left.right, g.right);
  res := case g { Empty => g, Node(gv, p, d) => case p { Empty => g, Node(pv, x, c) => case x { Empty => g, Node(xv, a, b) => Tree.Node(xv, a, Tree.Node(pv, b, Tree.Node(gv, c, d))) } } };
}
