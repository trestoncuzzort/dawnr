t 1
task f(a: array) returns (r: int)
  modifies a
  ensures true
{
  a := [1];
  r := 0;
}
