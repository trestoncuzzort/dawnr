t 1
task r2_s177(s: seq) returns (result: bool)
  requires forall k in [0, len(s)) . s[k] >= 0 and s[k] <= 11111111
  ensures result == (len(s) % 2 == 1)
{
  result := len(s) % 2 == 1;
}
