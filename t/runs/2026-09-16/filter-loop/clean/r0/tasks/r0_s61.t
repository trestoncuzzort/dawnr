t 1
task r0_s61(s: seq) returns (result: bool)
  requires forall k in [0, len(s)) . s[k] >= 0 and s[k] <= 11114111
  ensures result == (len(s) % 2 == 1)
{
  result := len(s) % 2 == 1;
}
