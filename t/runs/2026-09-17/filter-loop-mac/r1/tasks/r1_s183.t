t 1
task r1_s183(n: int) returns (r: int)
  requires n >= 0
  ensures r == n
{
  var i: int := 0;
  while i < n
    invariant 0 < i and i <= n
    decreases n - i
  {
    i := i + 1;
  }
  r := i;
}
