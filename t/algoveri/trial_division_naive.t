t 1
gate loops
task trial_division_naive(n: int) returns (res: bool)
  requires n >= 0
  ensures res == is_prime(n)
spec fun divides(d: int, n: int): bool
  decreases 0
= d != 0 and n % d == 0
spec fun is_prime(n: int): bool
  decreases 0
= n > 1 and (forall d in [2, n) . not divides(d, n))
lemma divisor_makes_composite(n: int, d: int)
  requires 2 <= d and d < n and n % d == 0
  ensures not is_prime(n)
{
  assert divides(d, n);
}
{
  if n < 2 {
    res := false;
  } else {
    var i: int := 2;
    while i < n
      invariant 2 <= i and i <= n
      invariant forall k in [2, i) . not divides(k, n)
      decreases n - i
    {
      if n % i == 0 {
        divisor_makes_composite(n, i);
        return false;
      } else {
      }
      i := i + 1;
    }
    res := true;
  }
}
