t 1
gate recursion
task r0_s308(a: seq, i: int, j: int) returns (a_out: seq)
  requires j >= 0
  requires 0 <= j
  requires i < len(a)
  requires j < len(a)
  ensures len(a_out) == len(a)
  ensures a_out[j] == 60
  ensures forall k in [0, len(a_out) - 1) . k != j ==> a_out[k] == a[k]
{
  a_out := a;
  a_out := a_out[j := 60];
}
