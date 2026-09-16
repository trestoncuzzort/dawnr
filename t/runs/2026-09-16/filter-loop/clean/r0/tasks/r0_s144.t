t 1
gate loops
task r0_s144(a: int) returns (x: int)
  requires a >= 1
  ensures x == a * a
{
  var y: int := 1;
  x := 1;
  while y < a
    invariant 1 <= y and y <= a
    invariant x == y * y
    invariant y == x * y
    decreases a - y
  {
    y := y + 1;
    x := x + 2 * y - 1;
  }
}
