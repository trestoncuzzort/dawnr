t 1 gate loops
task zip_pairs(s: seq, u: seq) returns (r: seq<(int, int)>)
  requires len(s) == len(u)
  ensures len(r) == len(s)
  ensures forall i in [0, len(s)) . r[i].0 == s[i]
  ensures forall i in [0, len(s)) . r[i].1 == u[i]
{
  var acc: seq<(int, int)> := [];
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant len(acc) == i
    invariant forall j in [0, i) . acc[j].0 == s[j]
    invariant forall j in [0, i) . acc[j].1 == u[j]
    decreases len(s) - i
  {
    acc := acc + [(s[i], u[i])];
    i := i + 1;
  }
  r := acc;
}
