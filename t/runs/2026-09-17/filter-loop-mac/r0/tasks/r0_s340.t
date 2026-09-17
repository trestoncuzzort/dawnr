t 1
gate loops
task r0_s340(a: int) returns (x: int)
  requires a > 1
  ensures x == a * a
{
  var y: int := 1;
  x := 1;
  while y > 0
    invariant 1 <= y and y <= a
    invariant x >= 0
    decreases a - y
  {
    y := y + 1;
    x := x + 2 * y - 1;
  }
}
