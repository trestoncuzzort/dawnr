t 1
gate loops
task r0_s126(x: int, y: int) returns (r: int)
  requires x >= 0
  requires y >= 0
  ensures r == x + y
{
  var m: int := x;
  var n: int := y;
  r := 0;
  m := x;
  while m > 0
    invariant m >= 0
    invariant m * n + r == x * y * y
    invariant r >= 0
    decreases m - 0
  {
    r := r + n;
    m := m - 1;
  }
}
