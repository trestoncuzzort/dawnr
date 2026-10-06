t 1 task f(m: map<int, int>, b: bool) returns (r: int)
ensures true
{
  r := m[b];
}
