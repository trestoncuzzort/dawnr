t 0 task f(x: int) returns (r: int) ensures r == x
{
  if x { r := 0 } else { r := 1 }
}
