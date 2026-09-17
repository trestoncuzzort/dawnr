t 1
task r0_s229(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := 3 * x;
  r := y + x;
}
