datatype Tree = Nil | Node(val: int, is_red: bool, left: Tree, right: Tree)
t 1
task flip_colors(node: Tree) returns (res: Tree)
  requires case node { Nil => false, Node(val, is_red, left, right) => true }
  requires case node.left { Nil => false, Node(val, is_red, left, right) => true }
  requires case node.right { Nil => false, Node(val, is_red, left, right) => true }
  requires node.is_red != node.left.is_red
  requires node.left.is_red == node.right.is_red
  ensures case res { Nil => false, Node(val, is_red, left, right) => true }
  ensures case res.left { Nil => false, Node(val, is_red, left, right) => true }
  ensures case res.right { Nil => false, Node(val, is_red, left, right) => true }
  ensures view(res) == view(node)
  ensures is_bst(res) == is_bst(node)
  ensures black_height(res) == black_height(node)
  ensures res.is_red != node.is_red
  ensures res.left.is_red != node.left.is_red
spec fun view(tree: Tree): set
  decreases tree
= case tree { Nil => {}, Node(val, is_red, left, right) => union(union(view(left), view(right)), {val}) }
spec fun is_bst(tree: Tree): bool
  decreases tree
= case tree { Nil => true, Node(val, is_red, left, right) => (forall x in view(left) . x < val) and is_bst(left) and (forall x in view(right) . x > val) and is_bst(right) }
spec fun black_height(tree: Tree): int
  decreases tree
= case tree { Nil => 1, Node(val, is_red, left, right) => if black_height(left) != -1 and black_height(right) != -1 and black_height(left) == black_height(right) then (if not is_red then black_height(left) + 1 else black_height(left)) else -1 }
{
  res := case node { Nil => node, Node(v, c, l, r) => case l { Nil => node, Node(lv, lc, ll, lr) => case r { Nil => node, Node(rv, rc, rl, rr) => Tree.Node(v, not c, Tree.Node(lv, not lc, ll, lr), Tree.Node(rv, not rc, rl, rr)) } } };
}
