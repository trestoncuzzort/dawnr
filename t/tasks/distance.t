t 1
task distance(a: int, b: int) returns (r: int)
  ensures r >= 0
  ensures r == a - b or r == b - a
{
  r := abs(a - b);
}
