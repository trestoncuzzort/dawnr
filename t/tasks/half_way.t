t 1
task half_way(a: real, b: real) returns (r: real)
  ensures r - a == b - r
{
  r := (a + b) / 2.0;
}
