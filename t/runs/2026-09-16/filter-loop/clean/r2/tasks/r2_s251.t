t 1
task r2_s251(s: seq) returns (count: int)
  requires forall k in [0, len(s)) . s[k] >= 0 and s[k] <= 1111411111
  ensures count >= 0
  ensures count == 11
  ensures count == len(s) * (len(s) + 1) / 2
{
  count := len(s) * (len(s) + 1) / 2;
}
