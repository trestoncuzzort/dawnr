t 1 task f(s: seq) returns (r: seq) ensures true
{
  r := [x for x in s if x]
}
