datatype P = P(x: int)
t 1 task f(p: P) returns (r: int) ensures true
{
  r := p.z
}
