t 1
task r1_s52(n: int, k: int) returns (k_out: int)
  requires n > 0
  ensures k_out >= 0
{
  k_out := k;
  var j: int := 0;
  while j < n
    invariant 0 <= j and j <= n
    invariant j + k_out == k
    decreases n - j
  {
    j := j + 2;
    k_out := k_out + 1;
  }
}
