t 1
task r1_s201(s: seq) returns (count: int)
  requires forall k in [0, len(s)) . s[k] >= 0 and s[k] <= 1150
  ensures count >= 0
  ensures count == len(s)
{
  count := len(s);
}
