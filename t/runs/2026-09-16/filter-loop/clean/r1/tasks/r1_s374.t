t 1
gate loops
task r1_s374(x: int, y: int) returns (r: int)
  requires x >= 0
  ensures r >= 0
  ensures r == x + y
{
  var m: int := x;
  var n: int := y;
  r := 0;
  while m > 0
    invariant m >= 0
    invariant m * n + r == x * y
    invariant r >= 0
    decreases m - 0
  {
    r := r + n;
    m := m - 1;
  }
}
