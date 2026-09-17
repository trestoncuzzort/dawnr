t 1
task r1_s416(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := x / 2;
  r := y + x;
}
