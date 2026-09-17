t 1
task r1_s230(n: int, k: int) returns (k_out: int)
  requires n > 0
  requires k > n
  requires n > 0
  ensures k_out > n
{
  k_out := k;
  var i: int := 0;
  while i < n
    invariant 0 <= i and i <= n
    decreases n - i
  {
    i := i + 1;
  }
}
