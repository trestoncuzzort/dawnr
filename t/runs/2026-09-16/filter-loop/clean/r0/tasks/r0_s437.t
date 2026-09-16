t 1
gate loops
task r0_s437(x: int) returns (r: int)
  requires x >= 0
  ensures r >= 0
  ensures r == x + 1
{
  r := x + 1;
}
