t 1
task squares(n: int) returns (r: seq)
  requires n >= 0
  ensures len(r) == n
  ensures forall k in [0, n) . r[k] == k * k
{
  r := [i * i for i in [0, n)];
}
