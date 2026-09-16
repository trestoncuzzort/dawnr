t 1
gate recursion
task r0_s385(n: int) returns (r: int)
  requires n >= 0
  ensures r == fat(n)
spec fun fat(n_v: int): int
  decreases n_v
= if n_v >= 0 then if n_v == 0 then 1 else n_v * fat(n_v - 1) else 0
{
  var i: int := 0;
  r := 1;
  while i < n
    invariant 0 <= i and i <= n
    invariant r == fat(i)
    invariant r >= 0
    decreases n - i
  {
    i := i + 1;
    r := r + i;
  }
}
