t 1
task false_lemma(n: int) returns (r: int)
  requires n >= 0
  ensures r >= 2
spec fun pow2(k: int): int
  decreases k
= if k <= 0 then 1 else 2 * pow2(k - 1)
lemma pow2_ge2(k: int)
  requires k >= 0
  ensures pow2(k) >= 2
  decreases k
{
  if k > 0 {
    pow2_ge2(k - 1);
  } else {
  }
}
{
  pow2_ge2(n);
  r := pow2(n);
}
