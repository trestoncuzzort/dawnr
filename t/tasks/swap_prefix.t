t 1
task swap_prefix(s: seq, n: int) returns (r: seq)
  requires 0 <= n and n <= len(s)
  ensures len(r) == n
{
  r := s[0..n].swapcase();
}
