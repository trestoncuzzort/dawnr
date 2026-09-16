t 1
gate loops
task r2_s376(n: int) returns (sum: int)
  requires n >= 0
  requires n > 0
  ensures sum >= 0
  ensures sum == n * (n + 1) / 2
{
  sum := 0;
  var i: int := 0;
  while i < n
    invariant sum == i * (i + 1) * (i + 1)
    invariant i <= n
    decreases n - i
  {
    i := i + 1;
    sum := sum + 1;
  }
}
