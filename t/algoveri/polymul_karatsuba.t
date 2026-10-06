t 1
task poly_multiply_karatsuba(a: seq, b: seq) returns (res: seq)
  requires len(a) > 0
  requires len(b) > 0
  requires len(a) == len(b)
  requires exists k in [0, 11) . len(a) == pow(2, k)
  requires len(a) + len(b) <= 1000
  requires coeffs_bounded(a)
  requires coeffs_bounded(b)
  ensures len(res) == len(a) + len(b) - 1
  ensures forall k in [0, len(res)) . res[k] == spec_poly_mul_coeff(a, b, k)
spec fun to_int(s: seq): seq
  decreases 0
= s
spec fun coeffs_bounded(s: seq): bool
  decreases 0
= forall i in [0, len(s)) . -1000000 <= s[i] and s[i] <= 1000000
spec fun spec_convolution_sum(a: seq, b: seq, k: int, current_i: int): int
  decreases if current_i < 0 then 0 else current_i + 1
= if current_i < 0 then 0
  else (if current_i < len(a) and k - current_i < len(b) and k - current_i >= 0 then a[current_i] * b[k - current_i] else 0) + spec_convolution_sum(a, b, k, current_i - 1)
spec fun spec_poly_mul_coeff(a: seq, b: seq, k: int): int
  decreases 0
= spec_convolution_sum(a, b, k, k)
spec fun p2(n: int): bool
  decreases n
= n >= 1 and (n == 1 or (n % 2 == 0 and p2(n / 2)))
spec fun at0(z: seq, j: int): int
  decreases 0
= if 0 <= j and j < len(z) then z[j] else 0
spec fun kc(z0: seq, z1: seq, z2: seq, m: int, k: int): int
  decreases 0
= at0(z0, k) + (at0(z1, k - m) - at0(z0, k - m) - at0(z2, k - m)) + at0(z2, k - m - m)
spec fun is_prod(z: seq, x: seq, y: seq): bool
  decreases 0
= len(z) == len(x) + len(y) - 1 and (forall j in [0, len(z)) . z[j] == spec_poly_mul_coeff(x, y, j))
method vadd(x: seq, y: seq) returns (s: seq)
  requires len(x) == len(y)
  ensures len(s) == len(x)
  ensures forall q in [0, len(s)) . s[q] == x[q] + y[q]
{
  s := [];
  var i: int := 0;
  while i < len(x)
    invariant 0 <= i and i <= len(x)
    invariant len(s) == i
    invariant forall q in [0, i) . s[q] == x[q] + y[q]
    decreases len(x) - i
  {
    s := s + [x[i] + y[i]];
    i := i + 1;
  }
}
method combine(a: seq, b: seq, m: int, a0: seq, a1: seq, b0: seq, b1: seq, sa: seq, sb: seq, z0: seq, z1: seq, z2: seq) returns (r: seq)
  requires a == a0 + a1 and b == b0 + b1
  requires m == len(a0)
  requires len(a1) == m and len(b0) == m and len(b1) == m
  requires len(sa) == m and len(sb) == m
  requires forall q in [0, m) . sa[q] == a0[q] + a1[q]
  requires forall q in [0, m) . sb[q] == b0[q] + b1[q]
  requires is_prod(z0, a0, b0)
  requires is_prod(z1, sa, sb)
  requires is_prod(z2, a1, b1)
  ensures is_prod(r, a, b)
{
  r := [];
  var k: int := 0;
  while k < 4 * m - 1
    invariant 0 <= k and k <= 4 * m - 1
    invariant len(r) == k
    invariant forall x in [0, k) . r[x] == spec_poly_mul_coeff(a, b, x)
    decreases 4 * m - 1 - k
  {
    kara_coeff(a, b, m, a0, a1, b0, b1, sa, sb, z0, z1, z2, k);
    r := r + [kc(z0, z1, z2, m, k)];
    k := k + 1;
  }
}
method kmul(a: seq, b: seq) returns (r: seq)
  requires len(a) == len(b)
  requires p2(len(a))
  ensures is_prod(r, a, b)
  decreases len(a)
{
  if len(a) == 1 {
    conv_single(a, b);
    r := [a[0] * b[0]];
  } else {
    p2_half(len(a));
    var m: int := len(a) / 2;
    var a0: seq := a[0..m];
    var a1: seq := a[m..len(a)];
    var b0: seq := b[0..m];
    var b1: seq := b[m..len(b)];
    var sa: seq := vadd(a0, a1);
    var sb: seq := vadd(b0, b1);
    var z0: seq := kmul(a0, b0);
    var z2: seq := kmul(a1, b1);
    var z1: seq := kmul(sa, sb);
    join_slices(a, m);
    join_slices(b, m);
    r := combine(a, b, m, a0, a1, b0, b1, sa, sb, z0, z1, z2);
  }
}
lemma conv_tail(a: seq, b: seq, k: int, lo: int, hi: int)
  requires -1 <= lo and lo <= hi
  requires lo >= len(a) - 1 or k <= lo or k - hi >= len(b)
  ensures spec_convolution_sum(a, b, k, hi) == spec_convolution_sum(a, b, k, lo)
  decreases hi - lo
{
  if lo < hi {
    conv_tail(a, b, k, lo, hi - 1);
  } else {
  }
}
lemma conv_last(a: seq, b: seq, k: int)
  ensures spec_poly_mul_coeff(a, b, k) == spec_convolution_sum(a, b, k, len(a) - 1)
{
  if k < 0 {
    conv_tail(a, b, k, -1, len(a) - 1);
  } else {
    if k <= len(a) - 1 {
      conv_tail(a, b, k, k, len(a) - 1);
    } else {
      conv_tail(a, b, k, len(a) - 1, k);
    }
  }
}
lemma conv_last_n(a: seq, b: seq, k: int, n: int)
  requires n == len(a)
  ensures spec_poly_mul_coeff(a, b, k) == spec_convolution_sum(a, b, k, n - 1)
{
  conv_last(a, b, k);
}
lemma conv_out(x: seq, y: seq, j: int)
  requires j >= len(x) + len(y) - 1
  ensures spec_poly_mul_coeff(x, y, j) == 0
{
  conv_last(x, y, j);
  conv_tail(x, y, j, -1, len(x) - 1);
}
lemma conv_single(x: seq, y: seq)
  requires len(x) == 1 and len(y) == 1
  ensures spec_poly_mul_coeff(x, y, 0) == x[0] * y[0]
{
  assert spec_convolution_sum(x, y, 0, -1) == 0;
  assert spec_convolution_sum(x, y, 0, 0) == x[0] * y[0] + spec_convolution_sum(x, y, 0, -1);
}
lemma cs_pre(x: seq, x2: seq, y: seq, k: int, i: int)
  requires -1 <= i and i < len(x)
  ensures spec_convolution_sum(x + x2, y, k, i) == spec_convolution_sum(x, y, k, i)
  decreases i + 1
{
  if i >= 0 {
    cs_pre(x, x2, y, k, i - 1);
  } else {
  }
}
lemma cs_catL(x: seq, x2: seq, y: seq, k: int, i: int)
  requires i >= len(x) - 1
  ensures spec_convolution_sum(x + x2, y, k, i) == spec_convolution_sum(x, y, k, len(x) - 1) + spec_convolution_sum(x2, y, k - len(x), i - len(x))
  decreases i - len(x) + 1
{
  if i == len(x) - 1 {
    cs_pre(x, x2, y, k, i);
  } else {
    cs_catL(x, x2, y, k, i - 1);
  }
}
lemma cs_catR(x: seq, y: seq, y2: seq, k: int, i: int)
  requires i >= -1
  ensures spec_convolution_sum(x, y + y2, k, i) == spec_convolution_sum(x, y, k, i) + spec_convolution_sum(x, y2, k - len(y), i)
  decreases i + 1
{
  if i >= 0 {
    cs_catR(x, y, y2, k, i - 1);
  } else {
  }
}
lemma mul_dist_l(r: int, p: int, q: int, c: int)
  requires r == p + q
  ensures r * c == p * c + q * c
{
}
lemma mul_dist_r(c: int, r: int, p: int, q: int)
  requires r == p + q
  ensures c * r == c * p + c * q
{
}
lemma cs_addL(x: seq, x2: seq, s: seq, y: seq, k: int, i: int)
  requires len(x2) == len(x) and len(s) == len(x)
  requires forall q in [0, len(x)) . s[q] == x[q] + x2[q]
  requires i >= -1
  ensures spec_convolution_sum(s, y, k, i) == spec_convolution_sum(x, y, k, i) + spec_convolution_sum(x2, y, k, i)
  decreases i + 1
{
  if i >= 0 {
    cs_addL(x, x2, s, y, k, i - 1);
    if i < len(x) and k - i < len(y) and k - i >= 0 {
      mul_dist_l(s[i], x[i], x2[i], y[k - i]);
    } else {
    }
  } else {
  }
}
lemma cs_addR(x: seq, y: seq, y2: seq, s: seq, k: int, i: int)
  requires len(y2) == len(y) and len(s) == len(y)
  requires forall q in [0, len(y)) . s[q] == y[q] + y2[q]
  requires i >= -1
  ensures spec_convolution_sum(x, s, k, i) == spec_convolution_sum(x, y, k, i) + spec_convolution_sum(x, y2, k, i)
  decreases i + 1
{
  if i >= 0 {
    cs_addR(x, y, y2, s, k, i - 1);
    if i < len(x) and k - i < len(y) and k - i >= 0 {
      mul_dist_r(x[i], s[k - i], y[k - i], y2[k - i]);
    } else {
    }
  } else {
  }
}
lemma conv_catL(x: seq, x2: seq, y: seq, k: int)
  ensures spec_poly_mul_coeff(x + x2, y, k) == spec_poly_mul_coeff(x, y, k) + spec_poly_mul_coeff(x2, y, k - len(x))
{
  conv_last_n(x + x2, y, k, len(x) + len(x2));
  cs_catL(x, x2, y, k, len(x) + len(x2) - 1);
  conv_last_n(x, y, k, len(x));
  conv_last_n(x2, y, k - len(x), len(x2));
}
lemma conv_catR(x: seq, y: seq, y2: seq, k: int)
  ensures spec_poly_mul_coeff(x, y + y2, k) == spec_poly_mul_coeff(x, y, k) + spec_poly_mul_coeff(x, y2, k - len(y))
{
  conv_last_n(x, y + y2, k, len(x));
  cs_catR(x, y, y2, k, len(x) - 1);
  conv_last_n(x, y, k, len(x));
  conv_last_n(x, y2, k - len(y), len(x));
}
lemma conv_addL(x: seq, x2: seq, s: seq, y: seq, k: int)
  requires len(x2) == len(x) and len(s) == len(x)
  requires forall q in [0, len(x)) . s[q] == x[q] + x2[q]
  ensures spec_poly_mul_coeff(s, y, k) == spec_poly_mul_coeff(x, y, k) + spec_poly_mul_coeff(x2, y, k)
{
  conv_last_n(s, y, k, len(x));
  cs_addL(x, x2, s, y, k, len(x) - 1);
  conv_last_n(x, y, k, len(x));
  conv_last_n(x2, y, k, len(x));
}
lemma conv_addR(x: seq, y: seq, y2: seq, s: seq, k: int)
  requires len(y2) == len(y) and len(s) == len(y)
  requires forall q in [0, len(y)) . s[q] == y[q] + y2[q]
  ensures spec_poly_mul_coeff(x, s, k) == spec_poly_mul_coeff(x, y, k) + spec_poly_mul_coeff(x, y2, k)
{
  conv_last_n(x, s, k, len(x));
  cs_addR(x, y, y2, s, k, len(x) - 1);
  conv_last_n(x, y, k, len(x));
  conv_last_n(x, y2, k, len(x));
}
lemma at0_conv(z: seq, x: seq, y: seq, j: int)
  requires is_prod(z, x, y)
  ensures at0(z, j) == spec_poly_mul_coeff(x, y, j)
{
  if j >= len(z) {
    conv_out(x, y, j);
  } else {
  }
}
lemma kara_d1(a: seq, b: seq, m: int, a0: seq, a1: seq, b0: seq, b1: seq, k: int)
  requires a == a0 + a1 and b == b0 + b1
  requires m == len(a0)
  requires len(b0) == m
  ensures spec_poly_mul_coeff(a, b, k) == spec_poly_mul_coeff(a0, b0, k) + spec_poly_mul_coeff(a0, b1, k - m) + spec_poly_mul_coeff(a1, b0, k - m) + spec_poly_mul_coeff(a1, b1, k - m - m)
{
  conv_catL(a0, a1, b0 + b1, k);
  conv_catR(a0, b0, b1, k);
  conv_catR(a1, b0, b1, k - m);
}
lemma kara_d2(m: int, a0: seq, a1: seq, b0: seq, b1: seq, sa: seq, sb: seq, j: int)
  requires m == len(a0)
  requires len(a1) == m and len(b0) == m and len(b1) == m
  requires len(sa) == m and len(sb) == m
  requires forall q in [0, m) . sa[q] == a0[q] + a1[q]
  requires forall q in [0, m) . sb[q] == b0[q] + b1[q]
  ensures spec_poly_mul_coeff(sa, sb, j) == spec_poly_mul_coeff(a0, b0, j) + spec_poly_mul_coeff(a0, b1, j) + spec_poly_mul_coeff(a1, b0, j) + spec_poly_mul_coeff(a1, b1, j)
{
  conv_addL(a0, a1, sa, sb, j);
  conv_addR(a0, b0, b1, sb, j);
  conv_addR(a1, b0, b1, sb, j);
}
lemma kara_coeff(a: seq, b: seq, m: int, a0: seq, a1: seq, b0: seq, b1: seq, sa: seq, sb: seq, z0: seq, z1: seq, z2: seq, k: int)
  requires a == a0 + a1 and b == b0 + b1
  requires m == len(a0)
  requires len(a1) == m and len(b0) == m and len(b1) == m
  requires len(sa) == m and len(sb) == m
  requires forall q in [0, m) . sa[q] == a0[q] + a1[q]
  requires forall q in [0, m) . sb[q] == b0[q] + b1[q]
  requires is_prod(z0, a0, b0)
  requires is_prod(z1, sa, sb)
  requires is_prod(z2, a1, b1)
  ensures kc(z0, z1, z2, m, k) == spec_poly_mul_coeff(a, b, k)
{
  at0_conv(z0, a0, b0, k);
  at0_conv(z0, a0, b0, k - m);
  at0_conv(z1, sa, sb, k - m);
  at0_conv(z2, a1, b1, k - m);
  at0_conv(z2, a1, b1, k - m - m);
  kara_d1(a, b, m, a0, a1, b0, b1, k);
  kara_d2(m, a0, a1, b0, b1, sa, sb, k - m);
}
lemma join_slices(s: seq, m: int)
  requires 0 <= m and m <= len(s)
  ensures s[0..m] + s[m..len(s)] == s
{
}
lemma p2_half(n: int)
  requires p2(n) and n != 1
  ensures n >= 2 and n % 2 == 0 and p2(n / 2)
{
}
lemma p2_pow(m: int)
  requires m >= 0
  ensures forall k in [0, m) . p2(pow(2, k))
  decreases m
{
  if m > 0 {
    p2_pow(m - 1);
  } else {
  }
}
lemma exists_p2(n: int)
  requires exists k in [0, 11) . n == pow(2, k)
  ensures p2(n)
{
  p2_pow(11);
}
{
  exists_p2(len(a));
  if len(a) == 1 {
    conv_single(a, b);
    res := [a[0] * b[0]];
  } else {
    res := kmul(a, b);
  }
}
