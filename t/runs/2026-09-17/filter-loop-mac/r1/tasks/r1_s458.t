t 1
task r1_s458(s: seq) returns (count: int)
  requires forall k in [0, len(s)) . s[k] >= 0 and s[k] <= 11411111
  ensures count >= 0
  ensures count == len(s) * (len(s) + 1) / 2
{
  count := len(s) * (len(s) + 1) / 2;
}
