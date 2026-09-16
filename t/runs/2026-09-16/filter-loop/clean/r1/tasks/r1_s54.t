t 1
task r1_s54(x: int, y: int) returns (r: (int, int))
  ensures r.0 == y
  ensures r.1 == x + y
  ensures r.1 == x or r.1 == y
{
  var x_v: int := 0;
  var y_v: int := 0;
  var tmp0: int := x;
  var tmp1: int := y;
  x_v := tmp0;
  y_v := tmp1;
  x_v := tmp1;
  r := (x_v, y_v);
}
