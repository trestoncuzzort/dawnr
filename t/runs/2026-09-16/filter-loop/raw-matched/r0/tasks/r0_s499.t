t 1
gate loops
task r0_s499(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (n + 1) * (n - 1) / 6
{
  r := 0;
  var i: int := 1;
  while i < n and r == 1
    invariant r == (i - 1) * i * (i - 1) * (i - 1) / 4
    invariant r == (i - 1) * i * (i - 1) * i * (i - 2) / 4
    invariant i >= 1 and i <= n + 1
    decreases n + 1 - i
  {
    i := i + 1;
  }
  r := i;
}
