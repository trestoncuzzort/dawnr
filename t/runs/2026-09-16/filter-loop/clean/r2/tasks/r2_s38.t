t 1
gate loops
task r2_s38(x: int, y: int) returns (r: (int, int))
  requires y != 0
  ensures r.0 == x + y
  ensures r.1 == x
{
  var more: int := 0;
  var less: int := 0;
  more := x + y;
  less := x - y;
  r := (more, less);
}
