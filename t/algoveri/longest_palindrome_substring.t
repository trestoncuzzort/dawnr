t 1
gate loops
task longest_palindromic_substring(s: seq) returns (res: (int, int))
  requires len(s) <= 1000000
  ensures res.0 >= 0 and res.1 >= 0
  ensures is_valid_subrange(s, res.0, res.1)
  ensures is_palindrome(s[res.0..res.0 + res.1])
  ensures forall i in [0, len(s) + 1) . no_longer(s, i, len(s), res.1)
spec fun is_palindrome(s: seq): bool
  decreases 0
= forall i in [0, len(s)) . s[i] == s[len(s) - 1 - i]
spec fun is_valid_subrange(s: seq, start: int, n: int): bool
  decreases 0
= 0 <= start and 0 <= n and start + n <= len(s)
spec fun no_longer(s: seq, i: int, e: int, m: int): bool
  decreases 0
= forall n in [0, e + 1) . (is_valid_subrange(s, i, n) and is_palindrome(s[i..i + n])) ==> n <= m
lemma nl_extend(s: seq, i: int, e: int, e2: int, m: int, m2: int)
  requires e2 == e + 1 and m <= m2
  requires no_longer(s, i, e, m)
  requires (is_valid_subrange(s, i, e2) and is_palindrome(s[i..i + e2])) ==> e2 <= m2
  ensures no_longer(s, i, e2, m2)
{
}
lemma nl_mono_all(s: seq, k: int, e: int, m: int, m2: int)
  requires 0 <= k and m <= m2
  requires forall a in [0, k) . no_longer(s, a, e, m)
  ensures forall a in [0, k) . no_longer(s, a, e, m2)
  decreases k
{
  if k > 0 {
    nl_mono_all(s, k - 1, e, m, m2);
    assert no_longer(s, k - 1, e, m);
    assert no_longer(s, k - 1, e, m2);
  } else {
  }
}
{
  var bi: int := 0;
  var bl: int := 0;
  var i: int := 0;
  while i != len(s) + 1
    invariant 0 <= i and i <= len(s) + 1
    invariant is_valid_subrange(s, bi, bl) and is_palindrome(s[bi..bi + bl])
    invariant forall a in [0, i) . no_longer(s, a, len(s), bl)
    decreases len(s) + 1 - i
  {
    var l: int := 0;
    while l != len(s) + 1
      invariant 0 <= l and l <= len(s) + 1
      invariant is_valid_subrange(s, bi, bl) and is_palindrome(s[bi..bi + bl])
      invariant no_longer(s, i, l - 1, bl)
      invariant forall a in [0, i) . no_longer(s, a, len(s), bl)
      decreases len(s) + 1 - l
    {
      var ok: bool := is_valid_subrange(s, i, l) and is_palindrome(s[i..i + l]);
      var nbl: int := max(bl, if ok then l else 0);
      nl_extend(s, i, l - 1, l, bl, nbl);
      nl_mono_all(s, i, len(s), bl, nbl);
      bi := if nbl != bl then i else bi;
      bl := nbl;
      l := l + 1;
    }
    i := i + 1;
  }
  res := (bi, bl);
}
