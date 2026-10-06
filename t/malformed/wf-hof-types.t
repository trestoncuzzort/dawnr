t 1 task f(s: seq) returns (r: int)
ensures true
{
  r := max_by(s, x => x > 0);
}
