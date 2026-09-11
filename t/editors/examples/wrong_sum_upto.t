t 1
gate loops
task wrong_sum_upto(n: int) returns (r: int)
  requires n >= 0
  ensures r == n
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant 2 * r == i * (i + 1)
    invariant i >= 0 and i <= n
    decreases n - i
  {
    i := i + 1;
    r := r + i;
  }
}
