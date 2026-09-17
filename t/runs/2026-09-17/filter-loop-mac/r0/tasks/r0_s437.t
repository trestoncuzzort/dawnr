t 1
gate loops
task r0_s437(n: int) returns (sum: int)
  requires n >= 0
  ensures sum == n * (n + 1) / 2
{
  sum := 0;
  var i: int := 0;
  while i < n
    invariant sum == i * (i + 1) / 2
    invariant sum == 6 * (i + 1) / 2
    decreases if i <= n then n - i else i - n
  {
    i := sum + 2 * i + 1;
    i := i + 1;
  }
}
