t 1
task r2_s476(a: seq, b: seq) returns (result: seq)
  requires len(a) == len(b)
  requires forall i in [0, len(b)) . b[i] != 0
  ensures len(result) == len(a)
  ensures forall i_v in [0, len(result)) . result[i_v] == a[i_v] / b[i_v]
{
  result := [];
  var i_v2: int := 0;
  while i_v2 < len(a)
    invariant 0 <= i_v2 and i_v2 <= len(a)
    invariant forall k_v2 in [0, i_v2) . result[k_v2] == a[k_v2] / b[k_v2]
    decreases len(a) - i_v2
  {
    result := result + [a[i_v2] / b[i_v2]];
    i_v2 := i_v2 + 1;
  }
}
