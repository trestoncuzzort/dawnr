datatype S = A(v: int) | B(v: bool)
t 1 task f(p: S) returns (r: int) ensures true
{
  r := p.v
}
