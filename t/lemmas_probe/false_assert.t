t 1
task false_assert(n: int) returns (r: int)
  requires n >= 0
  ensures r >= 0
lemma nonneg(k: int)
  requires k >= 0
  ensures k >= 0
{
  assert k >= 1;
}
{
  nonneg(n);
  r := n;
}
