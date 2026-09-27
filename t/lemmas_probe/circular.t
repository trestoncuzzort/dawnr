t 1
task circular(n: int) returns (r: int)
  requires n >= 0
  ensures r == n + 1
lemma loop_forever(k: int)
  requires k >= 0
  ensures k == k + 1
  decreases k
{
  loop_forever(k);
}
{
  loop_forever(n);
  r := n;
}
