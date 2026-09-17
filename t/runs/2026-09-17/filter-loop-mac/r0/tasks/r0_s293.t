t 1
gate loops
task r0_s293(x: int) returns (r: int)
  ensures r == 3 * x
{
  var a: int := x * 3;
  r := 3 * x;
}
