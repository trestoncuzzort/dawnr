t 1
task opaque_callee(x: int) returns (r: int)
  ensures r == x + 1
method inc(a: int) returns (b: int)
  ensures b > a
{
  b := a + 1;
}
{
  r := inc(x);
}
