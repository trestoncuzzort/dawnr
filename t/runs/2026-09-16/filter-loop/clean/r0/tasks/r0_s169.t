t 1
task r0_s169(a: seq, b: seq) returns (result: seq)
  requires len(a) == len(b)
  requires len(a) == len(b)
  ensures len(result) == len(a)
  ensures forall i in [0, len(result)) . result[i] == a[i] - b[i]
{
  result := [];
  var i_v: int := 0;
  while i_v < len(a)
    invariant 0 <= i_v and i_v <= len(a)
    invariant len(result) == i_v
    invariant forall k in [0, i_v) . result[k] == a[k] - b[k]
    decreases len(a) - i_v
  {
    result := result[i_v := a[i_v] - b[i_v]];
    i_v := i_v + 1;
  }
}
