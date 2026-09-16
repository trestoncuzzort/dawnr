t 1
task r2_s215(s: seq) returns (result: bool)
  requires forall i in [0, len(s)) . s[i] >= 0 and s[i] < 1141111111
  ensures result == (len(s) % 2 == 1)
{
  result := len(s) % 2 == 1;
}
