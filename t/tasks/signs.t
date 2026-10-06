t 1 gate loops
task signs(s: seq) returns (r: seq<bool>)
  ensures len(r) == len(s)
  ensures forall i in [0, len(s)) . r[i] == (s[i] >= 0)
{
  var acc: seq<bool> := [];
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant len(acc) == i
    invariant forall j in [0, i) . acc[j] == (s[j] >= 0)
    decreases len(s) - i
  {
    acc := acc + [s[i] >= 0];
    i := i + 1;
  }
  r := acc;
}
