t 1
task r1_s33(n: int) returns (y: int)
  requires n >= 0
  ensures y != 0
{
  y := 1;
}
