datatype Tree = Empty | Node(val: int, left: Tree, right: Tree)
t 1
gate recursion
task insert(tree: Tree, v: int) returns (res: Tree)
  requires v >= 0
  requires is_bst(tree)
  ensures is_bst(res)
  ensures view(res) == union(view(tree), {v})
  decreases tree
spec fun view(tree: Tree): set
  decreases tree
= case tree { Empty => {}, Node(val, left, right) => union(union(view(left), view(right)), {val}) }
spec fun is_bst(tree: Tree): bool
  decreases tree
= case tree { Empty => true, Node(val, left, right) => (forall x in view(left) . x < val) and is_bst(left) and (forall x in view(right) . x > val) and is_bst(right) }
{
  res := case tree { Empty => Tree.Node(v, Tree.Empty, Tree.Empty), Node(val, left, right) => if v < val then Tree.Node(val, insert(left, v), right) else if v > val then Tree.Node(val, left, insert(right, v)) else tree };
}
