t 1
gate loops
task r1_s30(n: int) returns (sum: int)
  requires n >= 0
  ensures sum == n * (n + 1)
{
  sum := 0;
  var i: int := 0;
  while i < n + 1
    invariant 0 <= i and i <= n
    invariant sum == (i + 1) / 2
    invariant i >= 0 and i <= n
    decreases n - i
  {
    sum := sum + 1;
    sum := sum + i;
  }
}
