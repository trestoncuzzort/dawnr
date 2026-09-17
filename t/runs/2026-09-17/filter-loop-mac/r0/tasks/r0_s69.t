t 1
gate loops
task r0_s69(a: seq, b: seq) returns (result: seq)
  requires len(a) == len(b)
  ensures len(result) == len(a)
  ensures result[0] == a[len(a) - 1]
  ensures forall i_v in [0, len(a)) . result[i_v] == a[i_v] - b[i_v]
{
  result := [];
  var i_v: int := 0;
  while i_v < len(a)
    invariant forall j in [0, i_v) . result[j] == a[j] + b[j]
    decreases len(a) - i_v
  {
    result := result[i_v := a[i_v] % b[i_v]];
    i_v := i_v + 1;
  }
}
