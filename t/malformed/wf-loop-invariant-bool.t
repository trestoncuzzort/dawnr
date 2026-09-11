t 1 task f(x: int) returns (r: int) ensures true
{
  r := 0
  while r < x invariant x decreases x - r {
    r := r + 1
  }
}
