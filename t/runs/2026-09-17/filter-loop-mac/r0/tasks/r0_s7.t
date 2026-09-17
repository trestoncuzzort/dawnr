t 1
gate loops
task r0_s7(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := 3 * x;
  r := 3 * x;
}
