t 1
gate loops
task fast_exponential(b: int, e: int) returns (res: int)
  requires b >= 0
  requires e >= 0
  requires spec_pow(b, e) <= 18446744073709551615
  ensures res == spec_pow(b, e)
  ensures res >= 0
spec fun spec_pow(b: int, e: int): int
  decreases e
= if e <= 0 then 1 else b * spec_pow(b, e - 1)
lemma pow_nonneg(b: int, e: int)
  requires b >= 0 and e >= 0
  ensures spec_pow(b, e) >= 0
  decreases e
{
  if e > 0 {
    pow_nonneg(b, e - 1);
  } else {
  }
}
lemma pow_square(b: int, k: int)
  requires k >= 0
  ensures spec_pow(b * b, k) == spec_pow(b, 2 * k)
  decreases k
{
  if k > 0 {
    pow_square(b, k - 1);
  } else {
  }
}
{
  res := 1;
  var base: int := b;
  var ex: int := e;
  while ex > 0
    invariant ex >= 0
    invariant res * spec_pow(base, ex) == spec_pow(b, e)
    decreases ex
  {
    if ex % 2 == 1 {
      res := res * base;
      ex := ex - 1;
    } else {
      pow_square(base, ex / 2);
      base := base * base;
      ex := ex / 2;
    }
  }
  pow_nonneg(b, e);
}
