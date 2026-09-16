t 1
task r1_s41(a: seq, b: seq) returns (result: seq)
  requires len(a) == len(b)
  ensures len(result) == len(a)
  ensures len(result) == len(a)
  ensures forall i in [0, len(result)) . result[i] == a[i] + b[i]
{
  result := seq(len(a), 0);
  var i_v: int := 0;
  while i_v < len(a)
    invariant 0 <= i_v and i_v <= len(a)
    invariant len(result) == len(a)
    invariant forall k in [0, i_v) . result[k] == a[k] / b[k]
    decreases len(a) - i_v
  {
    result := result + [a[i_v] - b[i_v]];
    i_v := i_v + 1;
  }
}
