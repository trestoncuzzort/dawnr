t 1
gate recursion
task r0_s466(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (n - 1) + 1
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant 2 * r == i * (i + 1)
    invariant i <= n
    decreases n - i
  {
    i := i + 1;
    r := r + i;
  }
}
