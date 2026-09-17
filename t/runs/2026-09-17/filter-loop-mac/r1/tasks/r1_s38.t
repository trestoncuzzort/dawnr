t 1
task r1_s38(s: seq) returns (count: int)
  requires forall k in [0, len(s)) . s[k] >= 0 and s[k] <= 1114111
  ensures count >= 0
{
  count := len(s);
}
