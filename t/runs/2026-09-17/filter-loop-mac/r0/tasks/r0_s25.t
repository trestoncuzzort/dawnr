t 1
task r0_s25(a: seq, b: seq) returns (result: seq)
  requires len(a) == len(b)
  requires forall k in [0, len(b)) . b[k] != 0
  ensures len(result) == len(a)
  ensures forall k in [0, len(result)) . result[k] == a[k] - b[k]
{
  result := [];
  var i_v: int := 0;
  while i_v < len(a)
    invariant 0 <= i_v and i_v <= len(a)
    invariant len(result) == i_v
    invariant forall k in [0, i_v) . result[k] == a[k] * b[k]
    decreases len(a) - i_v
  {
    result := result + [a[i_v] - b[i_v]];
    i_v := i_v + 1;
  }
}
