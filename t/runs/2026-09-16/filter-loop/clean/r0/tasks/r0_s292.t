t 1
gate loops
task r0_s292(x: int, y: int) returns (r: (int, int))
  ensures r.0 == y
  ensures r.1 == x
{
  var x_v: int := 0;
  var y_v: int := 0;
  var tmp0: int := x;
  var tmp1: int := y;
  x_v := tmp0;
  y_v := tmp1;
  y_v := tmp1;
  var tmp: int := y_v;
  x_v := y_v - x_v;
  y_v := y_v - x_v;
  r := (x_v, y_v);
}
