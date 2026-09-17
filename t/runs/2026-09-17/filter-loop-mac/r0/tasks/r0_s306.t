t 1
gate loops
task r0_s306(a: seq) returns (a_out: seq)
  ensures len(a_out) == len(a)
  ensures a_out[0] == a[len(a_out) - 1]
  ensures a_out[len(a_out) - 1] == a[0]
  ensures a_out[len(a_out) - 1] == a[0]
  ensures forall k in [1, len(a_out) - 1) . a_out[k] == a[k]
{
  a_out := a;
  var tmp: int := a_out[0];
  a_out := a_out[0 := a_out[len(a_out) - 1]];
  a_out := a_out[len(a_out) - 1 := tmp];
}
