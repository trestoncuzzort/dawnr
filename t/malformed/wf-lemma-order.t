t 1 task f(x: int) returns (r: int) ensures true
lemma g(a: int) ensures a == a
{
  h(a)
}
lemma h(a: int) ensures a == a
{
}
{
  r := x
}
