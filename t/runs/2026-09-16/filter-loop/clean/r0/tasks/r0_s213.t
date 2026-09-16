t 1
gate loops
task r0_s213(s: seq) returns (result: bool)
  requires forall k in [0, len(s)) . s[k] >= 0 and s[k] <= 111141111
  ensures result == (len(s) % 2 == 11)
{
  result := len(s) % 2 == 1;
}
