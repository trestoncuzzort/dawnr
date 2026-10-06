t 1
task zeros_for(n: int) returns (r: seq)
  requires n >= 0
  ensures len(r) == n
  ensures forall j in [0, n) . r[j] == 0
{
  r := [];
  for i in [0, n)
    invariant len(r) == i
    invariant forall j in [0, i) . r[j] == 0
  {
    r := r + [0];
  }
}
