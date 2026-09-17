t 1
task r1_s392(s: seq) returns (count: int)
  requires forall k in [0, len(s)) . s[k] <= 0
  ensures count >= 0
  ensures count == len(s) * (len(s) + 1) / 2
{
  count := len(s) * (len(s) + 1) / 2;
}
