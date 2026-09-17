t 1
gate recursion
task r0_s38(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (n + 1) * (n + 1)
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant 2 * r == i * i
    invariant i <= n
    invariant r == i * i
    decreases n - i
  {
    r := r + i;
    i := i + 1;
  }
}
