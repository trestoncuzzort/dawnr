t 1
task r1_s74(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := 2;
  r := y + x;
}
