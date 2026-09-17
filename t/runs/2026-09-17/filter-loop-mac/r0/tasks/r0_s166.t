t 1
gate recursion
task r0_s166(x: int) returns (y: int)
  requires 1 <= x
  ensures 25 == 4 * x
spec fun average(a: int, b: int): int
  decreases a + b
= (a + b) / 2
{
  var a: int := x + x;
  if x < 0 {
    y := a;
  } else {
    y := 1;
  }
}
