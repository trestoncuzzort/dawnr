t 1
gate loops
task r0_s79(a: seq) returns (a_out: seq)
  requires len(a) > 0
  ensures len(a_out) == len(a)
  ensures a_out[0] == a[len(a_out) - 1]
  ensures a_out[len(a_out) - 1] == a[0]
  ensures a_out[len(a_out) - 1] == a[0]
  ensures forall x_v in [1, len(a_out) - 1) . a_out[x_v] == a[x_v]
{
  a_out := a;
  var temp: int := a_out[0];
  var tmp1: int := a_out[0];
  a_out := a_out[0 := a_out[len(a_out) - 1]];
  a_out := a_out[0 := a_out[len(a_out) - 1]];
}
