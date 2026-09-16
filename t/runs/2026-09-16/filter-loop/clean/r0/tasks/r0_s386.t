t 1
gate quantifiers
task r0_s386(s: seq, x: int, n: int) returns (r: bool)
  requires forall j in [0, len(s)) . s[j] >= 0 and s[j] <= 1114111
  ensures r == (len(s) % 2 == 1)
{
  r := len(s) % 2 == 1;
}
