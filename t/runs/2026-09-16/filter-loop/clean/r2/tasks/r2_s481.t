t 1
task r2_s481(a: int, b: int) returns (result: int)
  requires a >= 0
  requires b >= 0
  ensures result == a / b
{
  result := a / b;
}
