t 1
task poly_multiply(a: seq, b: seq) returns (res: seq)
  requires len(a) > 0
  requires len(b) > 0
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
lemma conv_last_all(a: seq, b: seq, n: int)
  requires n >= 0
  ensures forall k in [0, n) . spec_poly_mul_coeff(a, b, k) == spec_convolution_sum(a, b, k, len(a) - 1)
  decreases n
{
  if n > 0 {
    conv_last_all(a, b, n - 1);
    conv_last(a, b, n - 1);
  } else {
  }
}
{
  res := seq(len(a) + len(b) - 1, 0);
  var i: int := 0;
  while i < len(a)
    invariant 0 <= i and i <= len(a)
    invariant len(res) == len(a) + len(b) - 1
    invariant forall k in [0, len(res)) . res[k] == spec_convolution_sum(a, b, k, i - 1)
    decreases len(a) - i
  {
    var j: int := 0;
    while j < len(b)
      invariant 0 <= j and j <= len(b)
      invariant len(res) == len(a) + len(b) - 1
      invariant forall k in [0, len(res)) . res[k] == spec_convolution_sum(a, b, k, i - 1) + (if k - i >= 0 and k - i < j then a[i] * b[k - i] else 0)
      decreases len(b) - j
    {
      res := res[i + j := res[i + j] + a[i] * b[j]];
      j := j + 1;
    }
    i := i + 1;
  }
  conv_last_all(a, b, len(res));
}
