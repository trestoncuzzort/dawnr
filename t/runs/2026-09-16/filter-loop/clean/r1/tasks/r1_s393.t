t 1
task r1_s393(n: int) returns (s: int)
  ensures s == n * (n + 1) / 2
{
  var n_v: int := 0;
  while n_v != n
    invariant 0 <= n_v and n_v <= n
    invariant s == n_v * (n_v + 1) / 2
    invariant s >= 0
    decreases if n_v <= n then n - n_v else n_v - n
  {
    s := s + n_v;
    s := s - n_v;
  }
}
