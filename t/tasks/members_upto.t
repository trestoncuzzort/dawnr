t 1
task members_upto(s: seq, n: int) returns (r: set)
  requires 0 <= n and n <= len(s)
  ensures forall i in [0, n) . s[i] in r
{
  r := toset(s[0..n]);
}
