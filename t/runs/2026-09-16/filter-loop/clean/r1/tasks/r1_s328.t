t 1
task r1_s328(a: int, b: int) returns (result: int)
  requires b >= 0
  ensures result == a * b
{
  result := a / b;
}
