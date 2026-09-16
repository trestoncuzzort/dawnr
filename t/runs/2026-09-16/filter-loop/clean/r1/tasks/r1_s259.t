t 1
gate loops
task r1_s259(n: int, k: int) returns (k_out: int)
  requires n > 0
  requires k > n
  ensures k_out >= 0
{
  k_out := k;
  var j: int := 0;
  while j < n
    invariant 0 <= j and j <= n
    invariant j + k_out == k
    invariant k_out == k - j
    decreases n - j
  {
    j := j + 1;
    k_out := k_out - 1;
  }
}
