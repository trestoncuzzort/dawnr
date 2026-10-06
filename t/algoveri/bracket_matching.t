t 1
gate loops
task bracket_match(s: seq) returns (res: bool)
  requires len(s) <= 1000000
  ensures res == is_matched(s)
spec fun char_weight(c: int): int
  decreases 0
= if c == 40 then 1 else if c == 41 then -1 else 0
spec fun total_weight(s: seq): int
  decreases len(s)
= if len(s) == 0 then 0 else char_weight(s[0]) + total_weight(s[1..])
spec fun valid_prefix_weights(s: seq): bool
  decreases 0
= forall i in [0, len(s) + 1) . total_weight(s[0..i]) >= 0
spec fun is_matched(s: seq): bool
  decreases 0
= total_weight(s) == 0 and valid_prefix_weights(s)
lemma weight_snoc(s: seq, i: int)
  requires 0 <= i and i < len(s)
  ensures total_weight(s[0..i + 1]) == total_weight(s[0..i]) + char_weight(s[i])
  decreases i
{
  if i > 0 {
    weight_snoc(s[1..], i - 1);
    assert s[0..i + 1][1..] == s[1..][0..i];
    assert s[0..i][1..] == s[1..][0..i - 1];
  } else {
  }
}
lemma slice_all(s: seq, n: int)
  requires n == len(s)
  ensures s[0..n] == s
{
}
{
  var c: int := 0;
  var m: int := 0;
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant c == total_weight(s[0..i])
    invariant forall k in [0, i + 1) . m <= total_weight(s[0..k])
    invariant exists k in [0, i + 1) . m == total_weight(s[0..k])
    decreases len(s) - i
  {
    weight_snoc(s, i);
    c := c + char_weight(s[i]);
    m := min(m, c);
    i := i + 1;
  }
  slice_all(s, i);
  res := m >= 0 and c == 0;
}
