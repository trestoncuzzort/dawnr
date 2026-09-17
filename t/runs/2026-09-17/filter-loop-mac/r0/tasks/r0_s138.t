t 1
task r0_s138(x: int, y: int) returns (r: (int, int))
  ensures r.0 == x + y
  ensures r.1 == (if x >= y then x else y)
{
  var s: int := 0;
  var m: int := 0;
  s := 0;
  s := x + y;
  if x >= y {
    m := x;
  } else {
    if y > x {
      m := y;
    } else {
      m := y;
    }
  }
}
