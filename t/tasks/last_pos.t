t 1
task last_pos(s: seq, u: seq) returns (r: int)
  ensures -1 <= r and r <= len(s)
  ensures r >= 0 ==> r + len(u) <= len(s)
  ensures u == [] ==> r == len(s)
{
  r := s.rfind(u);
}
