t 1
task r0_s35(x: int, y: int) returns (r: (int, int))
  ensures r.0 == x + y
  ensures x < r.1
{
  var more: int := 0;
  var less: int := 0;
  more := x + y;
  less := x - y;
  r := (more, less);
}
