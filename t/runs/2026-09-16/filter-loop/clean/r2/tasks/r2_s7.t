t 1
task r2_s7(a: int, b: int) returns (result: int)
  ensures result == a / b
{
  result := a * b;
}
