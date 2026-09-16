t 1
task r1_s127(a: int, b: int) returns (result: int)
  ensures result == a
{
  result := a * b;
}
