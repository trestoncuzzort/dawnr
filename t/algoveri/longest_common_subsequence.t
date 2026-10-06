t 1
task solve_longest_common_subsequence(s: seq, u: seq) returns (r: int)
  requires len(s) <= 3000
  requires len(u) <= 3000
  ensures r == lcs_spec(s, u)
  ensures r >= 0
spec fun max(a: int, b: int): int
  decreases 0
= if a > b then a else b
spec fun lcs_spec(s1: seq, s2: seq): int
  decreases len(s1) + len(s2)
= if len(s1) == 0 or len(s2) == 0 then 0
  else if s1[len(s1) - 1] == s2[len(s2) - 1] then 1 + lcs_spec(s1[0..len(s1) - 1], s2[0..len(s2) - 1])
  else max(lcs_spec(s1[0..len(s1) - 1], s2), lcs_spec(s1, s2[0..len(s2) - 1]))
lemma lcs_step(s: seq, u: seq, i: int, j: int)
  requires 1 <= i and i <= len(s) and 1 <= j and j <= len(u)
  ensures lcs_spec(s[0..i], u[0..j]) == (if s[i - 1] == u[j - 1] then 1 + lcs_spec(s[0..i - 1], u[0..j - 1]) else max(lcs_spec(s[0..i - 1], u[0..j]), lcs_spec(s[0..i], u[0..j - 1])))
{
  assert s[0..i][0..i - 1] == s[0..i - 1];
  assert u[0..j][0..j - 1] == u[0..j - 1];
}
lemma lcs_nonneg(s1: seq, s2: seq)
  ensures lcs_spec(s1, s2) >= 0
  decreases len(s1) + len(s2)
{
  if len(s1) > 0 and len(s2) > 0 {
    lcs_nonneg(s1[0..len(s1) - 1], s2[0..len(s2) - 1]);
    lcs_nonneg(s1[0..len(s1) - 1], s2);
    lcs_nonneg(s1, s2[0..len(s2) - 1]);
  } else {
  }
}
lemma full_slice(s: seq, m: int)
  requires m == len(s)
  ensures s[0..m] == s
{
}
{
  var prev: seq := seq(len(u) + 1, 0);
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant len(prev) == len(u) + 1
    invariant forall j in [0, len(u) + 1) . prev[j] == lcs_spec(s[0..i], u[0..j])
    decreases len(s) - i
  {
    var cur: seq := [0];
    var j: int := 1;
    while j <= len(u)
      invariant 1 <= j and j <= len(u) + 1
      invariant len(cur) == j
      invariant forall x in [0, j) . cur[x] == lcs_spec(s[0..i + 1], u[0..x])
      decreases len(u) + 1 - j
    {
      lcs_step(s, u, i + 1, j);
      if s[i] == u[j - 1] {
        cur := cur + [prev[j - 1] + 1];
      } else {
        cur := cur + [max(prev[j], cur[j - 1])];
      }
      j := j + 1;
    }
    prev := cur;
    i := i + 1;
  }
  lcs_nonneg(s, u);
  full_slice(s, i);
  full_slice(u, len(u));
  r := prev[len(u)];
}
