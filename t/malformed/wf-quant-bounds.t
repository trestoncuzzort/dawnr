t 1 task f(x: int) returns (r: int) ensures forall i in [true, x) . i > 0
{
  r := x
}
