datatype D = A(x: int) | B(x: bool)
t 1
task f(d: D) returns (r: int)
  ensures r == 0
{
  r := 0;
}
