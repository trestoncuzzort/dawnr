t 1
task r0_s68(x: int, y: int) returns (z: int)
  requires y >= 0
  ensures z >= 0
  ensures z == x + y
{
  var a: int := x;
  var b: int := 0;
  a := x + x;
  if x < 20 {
    a := x + x;
  } else {
    b := 32 - 1;
  }
}
