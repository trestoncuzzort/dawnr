t 1
task r2_s236(x: int, y: int) returns (r: (int, int))
  ensures r.0 == y
  ensures r.1 == x - y
{
  var more: int := 0;
  var less: int := 0;
  more := x + y;
  less := x - y;
  r := (more, less);
}
