t 1
task r1_s87(s: seq) returns (count: int)
  requires forall i in [0, len(s)) . s[i] >= 0
  ensures count >= 0
  ensures count == len(s) * (len(s) + 1) / 2
{
  count := len(s) * (len(s) + 1) / 2;
}
