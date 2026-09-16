t 1
gate loops
task r0_s68(n: int) returns (sum: int)
  requires n >= 0
  ensures sum == n * (n + 1) / 2
{
  sum := 0;
  var i: int := 0;
  while i < n
    invariant sum == i * (i + 1)
    invariant sum == i * (i + 1) / 2
    invariant sum >= 0
    decreases n - i
  {
    sum := sum + 2 * i + 1;
    i := i + 1;
  }
}
