t 1
gate loops
task r1_s471(n: int, k: int) returns (k_out: int)
  requires n > 0
  ensures k_out > 0
  ensures k_out <= k
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
