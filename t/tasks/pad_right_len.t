t 1
task pad_right_len(s: seq, w: int) returns (r: seq)
  ensures len(r) == max(len(s), w)
  ensures forall i in [0, len(s)) . r[i] == s[i]
  ensures forall i in [len(s), len(r)) . r[i] == 32
{
  r := s.ljust(w, 32);
}
