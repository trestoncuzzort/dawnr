t 1
gate recursion
task r0_s18(x: int, y: int) returns (r: (int, int))
  requires x >= 0
  ensures r.0 == x + y
  ensures r.1 == (if x >= y then x else y)
{
  var s: int := 0;
  var m: int := 0;
  s := 0;
  m := x + y;
  if x > y {
    m := x;
  } else {
    m := y;
  }
}
