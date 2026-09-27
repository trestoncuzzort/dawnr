t 1 task f(x: int) returns (r: int) ensures true
lemma g(a: int) ensures a == a
{
  g(a - 1)
}
{
  r := x
}
