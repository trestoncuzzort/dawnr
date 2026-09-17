t 1
task r1_s397(x: int, y: int) returns (r: int)
  ensures r == 3 * x
{
  var a: int := x * 3;
  r := y + x;
}
