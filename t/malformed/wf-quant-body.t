t 1 task f(x: int) returns (r: int) ensures forall i in [0, x) . i
{
  r := x
}
