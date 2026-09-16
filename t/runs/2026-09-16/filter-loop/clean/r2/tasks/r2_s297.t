t 1
gate loops
task r2_s297(x: int, y: int) returns (r: (int, int))
  requires x > 0
  requires y >= 0
  ensures r.0 <= x
  ensures x < r.1
  ensures r.1 <= y
{
  var more: int := 0;
  var less: int := 0;
  more := x + y;
  less := x - y;
  r := (more, less);
}
