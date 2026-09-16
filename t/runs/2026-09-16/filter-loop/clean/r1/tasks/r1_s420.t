t 1
task r1_s420(a: seq, b: seq) returns (result: seq)
  ensures len(result) == len(a)
  ensures len(result) == len(a)
  ensures forall i_v in [0, len(result)) . result[i_v] == a[i_v] / b[i_v]
{
  result := [];
  var i_v2: int := 0;
  while i_v2 < len(a)
    invariant 0 <= i_v2 and i_v2 <= len(a)
    invariant len(result) == len(a)
    invariant forall k in [0, i_v2) . result[k] == a[k] / b[k]
    decreases len(a) - i_v2
  {
    result := result + [a[i_v2] / b[i_v2]];
    i_v2 := i_v2 + 1;
  }
}
