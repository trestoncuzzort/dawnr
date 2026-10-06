t 1 task f(s: seq) returns (r: int)
ensures true
{
  r := len([x => x for y in s]);
}
