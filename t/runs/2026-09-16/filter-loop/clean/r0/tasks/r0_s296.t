t 1
task r0_s296(s: seq) returns (result: bool)
  requires forall k in [0, len(s)) . s[k] >= 0 and s[k] <= 1111411111
  ensures result == (len(s) % 2 == 1)
{
  result := len(s) % 2 == 1;
}
