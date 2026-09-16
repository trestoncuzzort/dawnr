t 1
task r2_s448(x: int, y: int) returns (r: (int, int))
  requires y >= 0
  requires y >= 0
  ensures r.0 == x / y
{
  var more: int := 0;
  var less: int := 0;
  more := x + y;
  less := x - y;
  r := (more, less);
}
