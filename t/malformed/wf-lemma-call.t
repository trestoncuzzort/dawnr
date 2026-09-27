t 1 task f(x: int) returns (r: int) ensures true
lemma g(a: int) ensures a == a
{
}
{
  g(x, x);
  r := x
}
