t 1 task f(x: int) returns (r: int) ensures true
{
  r := 0
  while r < x decreases true {
    r := r + 1
  }
}
