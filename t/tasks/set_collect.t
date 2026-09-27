t 1 gate loops
task set_collect(s: seq) returns (r: set)
  ensures card(r) <= len(s)
  ensures forall i in [0, len(s)) . s[i] in r
{
  var acc: set := {};
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant card(acc) <= i
    invariant forall j in [0, i) . s[j] in acc
    decreases len(s) - i
  {
    acc := union(acc, {s[i]});
    i := i + 1;
  }
  r := acc;
}
