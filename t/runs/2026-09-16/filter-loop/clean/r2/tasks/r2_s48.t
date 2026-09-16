t 1
gate loops
task r2_s48(x: int, y: int) returns (r: (int, int))
  ensures r.0 == x + y
  ensures r.1 == x
  ensures r.1 == x
{
  var z: int := 0;
  var err: bool := false;
  if y != 42 {
    z := x / (42 - y);
    z := 42 - x;
  } else {
    z := y - 1;
  }
}
