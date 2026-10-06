t 1
gate loops
task integer_exponential(b: int, e: int) returns (res: int)
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
{
  res := 1;
  var i: int := 0;
  while i < e
    invariant 0 <= i and i <= e
    invariant res == spec_pow(b, i)
    decreases e - i
  {
    res := res * b;
    i := i + 1;
  }
  pow_nonneg(b, e);
}
