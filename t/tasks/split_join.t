t 1
task split_join(s: seq, c: int) returns (r: seq)
  ensures r == s
  ensures [c].join(s.split(c)) == s
{
  var trimmed: seq := s.strip();
  var rebuilt: seq := [c].join(s.split(c));
  r := rebuilt;
}
