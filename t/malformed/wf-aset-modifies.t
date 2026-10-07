t 1
task f(a: array) returns (r: int)
  requires len(a) > 0
  ensures true
{
  a[0] := 1;
  r := 0;
}
