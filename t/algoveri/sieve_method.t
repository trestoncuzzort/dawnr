t 1
gate loops
task sieve_method(n: int) returns (primes: seq<bool>)
  requires 0 <= n and n <= 100000
  ensures len(primes) == n
  ensures forall i in [0, n) . primes[i] == is_prime(i)
spec fun divides(d: int, m: int): bool
  decreases 0
= d != 0 and m % d == 0
spec fun is_prime(m: int): bool
  decreases 0
= m > 1 and (forall d in [2, m) . not divides(d, m))
spec fun free_f(m: int, i: int): bool
  decreases 0
= m >= 2 and (forall d in [2, i) . d >= m or not divides(d, m))
spec fun sieve_ok(p: seq<bool>, n: int, i: int): bool
  decreases 0
= len(p) == n and (forall k in [0, n) . p[k] == free_f(k, i))
lemma mul_ge0(a: int, b: int)
  requires a >= 0 and b >= 0
  ensures a * b >= 0
  decreases b
{
  if b > 0 {
    mul_ge0(a, b - 1);
  } else {
  }
}
lemma mul_mono(a: int, x: int, y: int)
  requires a >= 0 and x <= y
  ensures a * x <= a * y
{
  mul_ge0(a, y - x);
}
lemma mul_subst(a: int, b: int, x: int)
  requires a == b
  ensures a * x == b * x
{
}
lemma mono_imp(a: int, x: int, y: int)
  requires a >= 0
  ensures x <= y ==> a * x <= a * y
{
  if x <= y {
    mul_mono(a, x, y);
  } else {
  }
}
lemma sqmono_imp(x: int, y: int)
  requires x >= 0
  ensures x <= y ==> x * x <= y * y
{
  if x <= y {
    mul_mono(x, x, y);
    mul_mono(y, x, y);
  } else {
  }
}
lemma mul_diff_pos(d: int, x: int, y: int)
  requires d >= 1
  ensures x < y ==> d * x + d <= d * y
  decreases y - x
{
  if x < y {
    if y - x > 1 {
      mul_diff_pos(d, x, y - 1);
    } else {
    }
  } else {
  }
}
lemma uniq_core(d: int, q: int, qq: int, r: int, rr: int)
  requires d >= 1 and d * q + r == d * qq + rr
  requires 0 <= r and r < d and 0 <= rr and rr < d
  ensures q == qq and r == rr
{
  mul_diff_pos(d, q, qq);
  mul_diff_pos(d, qq, q);
}
lemma euclid(a: int, d: int)
  requires d > 0
  ensures a == d * (a / d) + a % d and 0 <= a % d and a % d < d
{
}
lemma mod_unique(a: int, d: int, q: int, r: int)
  requires d > 0 and a == d * q + r and 0 <= r and r < d
  ensures a % d == r and a / d == q
{
  euclid(a, d);
  uniq_core(d, q, a / d, r, a % d);
}
lemma div_mul(d: int, c: int)
  requires d >= 1
  ensures divides(d, d * c)
{
  mod_unique(d * c, d, c, 0);
}
lemma between_scan(i: int, c: int, k: int)
  requires i >= 1 and i * c < k
  ensures forall y in [k, i * c + i) . not divides(i, y)
  decreases i * c + i - k
{
  if k < i * c + i {
    mod_unique(k, i, c, k - i * c);
    between_scan(i, c, k + 1);
  } else {
  }
}
lemma mult_facts(i: int, c: int)
  requires i >= 1
  ensures divides(i, i * c)
  ensures forall y in [i * c + 1, i * c + i) . not divides(i, y)
{
  div_mul(i, c);
  between_scan(i, c, i * c + 1);
}
lemma sq_lt(i: int, n: int)
  requires 2 <= i and i * i < n
  ensures i < n
{
  mul_mono(i, 1, i);
}
lemma free_succ_all(n: int, i: int)
  requires 2 <= i
  ensures forall k in [0, n) . free_f(k, i + 1) == (free_f(k, i) and (i >= k or not divides(i, k)))
{
}
lemma prime_free(k: int, i: int)
  requires is_prime(k)
  ensures free_f(k, i)
{
}
lemma init_ok(p: seq<bool>, n: int)
  requires len(p) == n
  requires forall k in [0, n) . p[k] == (k >= 2)
  ensures sieve_ok(p, n, 2)
{
}
lemma sq_cut(k: int, i: int)
  requires 2 <= i and i < k and divides(i, k) and free_f(k, i)
  ensures i * i <= k
{
  euclid(k, i);
  mono_imp(i, k / i, 0);
  mono_imp(i, k / i, 1);
  mod_unique(k, k / i, i, 0);
  assert divides(k / i, k);
  mono_imp(k / i, 2, i);
  mono_imp(i, i, k / i);
}
lemma sq_cut_all(n: int, i: int, k: int)
  requires 2 <= i and 0 <= k
  ensures forall y in [k, n) . (i < y and divides(i, y) and free_f(y, i)) ==> i * i <= y
  decreases n - k
{
  if k < n {
    if i < k and divides(i, k) and free_f(k, i) {
      sq_cut(k, i);
    } else {
    }
    sq_cut_all(n, i, k + 1);
  } else {
  }
}
lemma div_trans(k: int, i: int, d: int)
  requires 1 <= i and 1 <= d and divides(i, k) and divides(d, i)
  ensures divides(d, k)
{
  euclid(k, i);
  euclid(i, d);
  mul_subst(i, d * (i / d), k / i);
  mod_unique(k, d, (i / d) * (k / i), 0);
}
lemma div_scan(k: int, i: int, d: int)
  requires 2 <= i and i < k and divides(i, k) and free_f(k, i)
  requires 2 <= d and d <= i
  ensures forall y in [d, i) . y >= i or not divides(y, i)
  decreases i - d
{
  if d < i {
    if divides(d, i) {
      div_trans(k, i, d);
    } else {
    }
    div_scan(k, i, d + 1);
  } else {
  }
}
lemma skip_all(n: int, i: int, k: int)
  requires 2 <= i and 0 <= k
  requires not free_f(i, i)
  ensures forall y in [k, n) . not (i < y and divides(i, y) and free_f(y, i))
  decreases n - k
{
  if k < n {
    if i < k and divides(i, k) and free_f(k, i) {
      div_scan(k, i, 2);
    } else {
    }
    skip_all(n, i, k + 1);
  } else {
  }
}
lemma step_skip(p: seq<bool>, n: int, i: int)
  requires 2 <= i and sieve_ok(p, n, i)
  requires i < n and not p[i]
  ensures sieve_ok(p, n, i + 1)
{
  skip_all(n, i, 0);
  free_succ_all(n, i);
}
lemma step_marked(p: seq<bool>, r: seq<bool>, n: int, i: int)
  requires 2 <= i and sieve_ok(p, n, i)
  requires len(r) == n
  requires forall k in [0, n) . r[k] == (p[k] and not (i * i <= k and divides(i, k)))
  ensures sieve_ok(r, n, i + 1)
{
  sq_cut_all(n, i, 0);
  free_succ_all(n, i);
  mul_mono(i, 2, i);
}
lemma comp_witness(k: int, i: int, d: int)
  requires 2 <= i and 2 <= d and d < k and divides(d, k) and k < i * i
  ensures not free_f(k, i)
{
  euclid(k, d);
  mono_imp(d, k / d, 0);
  mono_imp(d, k / d, 1);
  if d <= k / d {
    mono_imp(d, d, k / d);
    sqmono_imp(i, d);
  } else {
    mod_unique(k, k / d, d, 0);
    assert divides(k / d, k);
    mono_imp(k / d, k / d, d);
    sqmono_imp(i, k / d);
  }
}
lemma comp_scan(k: int, i: int, d: int)
  requires 2 <= i and 2 <= k and k < i * i and free_f(k, i) and 2 <= d
  ensures forall y in [d, k) . not divides(y, k)
  decreases k - d
{
  if d < k {
    if divides(d, k) {
      comp_witness(k, i, d);
    } else {
    }
    comp_scan(k, i, d + 1);
  } else {
  }
}
lemma done_scan(p: seq<bool>, n: int, i: int, k: int)
  requires 2 <= i and sieve_ok(p, n, i) and n <= i * i and 0 <= k
  ensures forall y in [k, n) . p[y] == is_prime(y)
  decreases n - k
{
  if k < n {
    if k >= 2 and free_f(k, i) {
      comp_scan(k, i, 2);
    } else {
    }
    if is_prime(k) {
      prime_free(k, i);
    } else {
    }
    done_scan(p, n, i, k + 1);
  } else {
  }
}
lemma sieve_done(p: seq<bool>, n: int, i: int)
  requires 2 <= i and sieve_ok(p, n, i) and n <= i * i
  ensures len(p) == n
  ensures forall k in [0, n) . p[k] == is_prime(k)
{
  done_scan(p, n, i, 0);
}
method mark_step(p: seq<bool>, n: int, i: int) returns (r: seq<bool>)
  requires 2 <= i and i * i < n
  requires sieve_ok(p, n, i)
  ensures sieve_ok(r, n, i + 1)
{
  r := p;
  var j: int := i * i;
  var c: int := i;
  while j < n
    invariant len(r) == n
    invariant j == i * c and i * i <= j
    invariant forall k in [0, n) . r[k] == (p[k] and not (i * i <= k and k < j and divides(i, k)))
    decreases n - j
  {
    mult_facts(i, c);
    r := r[j := false];
    j := j + i;
    c := c + 1;
  }
  step_marked(p, r, n, i);
}
{
  primes := [];
  var z: int := 0;
  while z < n
    invariant 0 <= z and z <= n
    invariant len(primes) == z
    invariant forall k in [0, z) . primes[k] == (k >= 2)
    decreases n - z
  {
    primes := primes + [z >= 2];
    z := z + 1;
  }
  init_ok(primes, n);
  var i: int := 2;
  while i * i < n
    invariant 2 <= i
    invariant sieve_ok(primes, n, i)
    decreases n - i * i
  {
    sq_lt(i, n);
    if primes[i] {
      primes := mark_step(primes, n, i);
    } else {
      step_skip(primes, n, i);
    }
    i := i + 1;
  }
  sieve_done(primes, n, i);
}
