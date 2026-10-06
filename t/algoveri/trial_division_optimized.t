t 1
gate loops
task trial_division_optimized(n: int) returns (res: bool)
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
lemma mul_mono(a: int, b: int, c: int)
  requires a <= b and c >= 0
  ensures a * c <= b * c
  decreases c
{
  if c > 0 {
    mul_mono(a, b, c - 1);
  } else {
  }
}
lemma quotient_unique(q: int, w: int, r: int)
  requires q >= 1 and q * w == r and 0 <= r and r < q
  ensures w == 0
{
  if w >= 1 {
    mul_mono(1, w, q);
  } else {
    if w <= -1 {
      mul_mono(w, -1, q);
    } else {
    }
  }
}
lemma mod_of_multiple(q: int, d: int)
  requires q >= 1
  ensures (q * d) % q == 0
{
  quotient_unique(q, d - (q * d) / q, (q * d) % q);
}
lemma no_divisor_above_root(n: int, i: int, d: int)
  requires n >= 2 and i >= 2 and i * i > n
  requires forall k in [2, i) . not divides(k, n)
  requires i <= d and d < n
  ensures not divides(d, n)
{
  if n % d == 0 {
    assert n / d >= 2;
    mul_mono(i, d, n / d);
    if n / d >= i {
      mul_mono(i, n / d, i);
    } else {
    }
    mod_of_multiple(n / d, d);
    assert divides(n / d, n);
  } else {
  }
}
lemma no_divisors_above_root(n: int, i: int, d: int)
  requires n >= 2 and i >= 2 and i * i > n
  requires forall k in [2, i) . not divides(k, n)
  requires i <= d and d <= n
  ensures forall e in [i, d) . not divides(e, n)
  decreases d - i
{
  if d > i {
    no_divisors_above_root(n, i, d - 1);
    no_divisor_above_root(n, i, d - 1);
  } else {
  }
}
lemma prime_beyond_root(n: int, i: int)
  requires n >= 2 and i >= 2 and i * i > n
  requires forall k in [2, i) . not divides(k, n)
  ensures is_prime(n)
{
  if i < n {
    no_divisors_above_root(n, i, n);
  } else {
  }
}
{
  if n < 2 {
    res := false;
  } else {
    var i: int := 2;
    while i * i <= n
      invariant 2 <= i
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
    prime_beyond_root(n, i);
    res := true;
  }
}
