datatype P = P(x: int)
t 1 task f() returns (r: bool) ensures true
{
  r := P.P(true) == P.P(1)
}
