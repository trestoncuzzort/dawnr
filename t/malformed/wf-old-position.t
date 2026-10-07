t 1
task f(a: array) returns (r: int)
  requires len(old(a)) > 0
  ensures true
{
  r := 0;
}
