t 1
task pad_right_len(s: seq, w: int) returns (r: seq)
  ensures len(r) == max(len(s), w)
{
  r := s.ljust(w);
}
