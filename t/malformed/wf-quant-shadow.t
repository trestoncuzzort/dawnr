t 1 task f(x: int) returns (r: int) ensures forall x in [0, x) . x > 0
{
  r := x
}
