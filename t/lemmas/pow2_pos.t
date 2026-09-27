t 1
task pow2_pos(n: int) returns (r: int)
  requires n >= 0
  ensures r >= 1
spec fun pow2(k: int): int
  decreases k
= if k <= 0 then 1 else 2 * pow2(k - 1)
lemma pow2_ge1(k: int)
  requires k >= 0
  ensures pow2(k) >= 1
  decreases k
{
  if k > 0 {
    pow2_ge1(k - 1);
  } else {
  }
}
{
  pow2_ge1(n);
  var p: int := pow2(n);
  r := p;
}
