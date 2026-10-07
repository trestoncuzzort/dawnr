t 1 task f(n: int) returns (r: bool) ensures true
{
  r := forall x in n . x > 0
}
