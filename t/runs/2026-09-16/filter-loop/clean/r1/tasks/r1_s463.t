t 1
gate recursion
task r1_s463(n: int) returns (sum: int)
  requires n >= 0
  requires n > 0
  ensures sum == n * n
{
  sum := 0;
  var i: int := 0;
  while i < n
    invariant 0 <= i and i <= n
    invariant sum == (i + 1) * (i + 1)
    invariant sum >= 0
    decreases n - i
  {
    sum := sum + i + 1;
    i := i + 1;
  }
}
