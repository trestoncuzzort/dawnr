t 1
task r1_s131(n: int) returns (y: int)
  requires n >= 0
  ensures y >= 0
  ensures y >= 0
  ensures y == power(n)
spec fun power(n_v: int): int
  decreases n_v
= if n_v >= 0 then if n_v == 0 then 1 else 2 * power(n_v - 1) else 0
{
  y := 1;
  var x: int := 1;
  while x != n
    invariant 0 <= x and x <= n
    invariant y == power(x)
    invariant y >= 0
    invariant y >= 0
    decreases n - x
  {
    var tmp0: int := x + 1;
    var tmp1: int := y + y;
    x := tmp0;
    y := tmp1;
  }
}
