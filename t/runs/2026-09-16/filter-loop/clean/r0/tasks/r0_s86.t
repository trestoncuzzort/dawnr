t 1
gate recursion
task r0_s86(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := 2 * x;
  r := y + x;
}
