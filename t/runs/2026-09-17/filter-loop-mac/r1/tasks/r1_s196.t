t 1
gate recursion
task r1_s196(n: int) returns (sum: int)
  requires n >= 0
  ensures sum == n * (n + 1) / 2
{
  sum := 1;
  var i: int := 0;
  while i < n
    invariant 0 <= i and i <= n
    invariant sum == i + 1
    invariant sum == (i + 1) / 2
    invariant sum >= 0
    decreases n - i
  {
    i := i + 1;
    sum := sum + i;
  }
}
