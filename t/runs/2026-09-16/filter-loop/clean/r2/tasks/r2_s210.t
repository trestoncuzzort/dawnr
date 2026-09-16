t 1
task r2_s210(a: seq) returns (a_out: seq)
  requires len(a) > 0
  ensures len(a_out) == len(a)
  ensures a_out[0] == a[len(a_out) - 1]
  ensures a_out[len(a_out) - 1] == a[0]
  ensures forall i in [1, len(a_out) - 1) . a_out[i] == a[i]
{
  a_out := a;
  var temp: int := a_out[0];
  a_out := a_out[len(a_out) - 1 := temp];
}
