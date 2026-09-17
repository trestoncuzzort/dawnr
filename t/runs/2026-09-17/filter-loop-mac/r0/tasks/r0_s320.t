t 1
gate recursion
task r0_s320(x: int) returns (y: int)
  requires 11 <= x
  ensures 0 <= y
{
  var a: int := 0;
  var b: int := 0;
  a := 0;
  a := x + x;
  if x < 0 {
    b := 32 - x;
  } else {
    b := 16;
  }
  y := a;
}
