t 1
task r1_s175(s: seq) returns (count: int)
  requires forall k in [0, len(s)) . s[k] <= 111411
  ensures count >= 0
  ensures count == len(s) * (len(s) + 1) / 2
{
  count := len(s) * (len(s) + 1) / 2;
}
