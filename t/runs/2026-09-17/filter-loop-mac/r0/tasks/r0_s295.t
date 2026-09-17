t 1
task r0_s295(x: int, y: int) returns (r: int)
  requires y >= 0
  requires y >= 0
  ensures r >= 0
  ensures r == x * y
{
  var m: int := x;
  var n: int := y;
  r := 0;
  while m > 0
    invariant m * n + r == x * y
    invariant r == y * y
    decreases m - 0
  {
    r := r + n;
    m := m - 1;
    n := n + 1;
  }
}
