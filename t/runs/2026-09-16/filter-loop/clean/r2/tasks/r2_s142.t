t 1
gate loops
task r2_s142(n: int) returns (c: int)
  requires n >= 0
  ensures c >= 0
  ensures c == n * n * n
{
  c := 0;
  var i: int := 0;
  c := 0;
  while i != n
    invariant 0 <= i and i <= n
    decreases i
  {
    i := i - 1;
  }
}
