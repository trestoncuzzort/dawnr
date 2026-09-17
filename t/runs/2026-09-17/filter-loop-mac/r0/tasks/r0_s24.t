t 1
gate loops
task r0_s24(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (n - 1) + 1
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant r == i * (i + 1)
    invariant i >= 0 and i <= n
    decreases n - i
  {
    i := i + 1;
    r := r + i;
  }
}
