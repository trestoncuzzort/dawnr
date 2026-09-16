t 1
gate loops
task r2_s213(x: int) returns (r: int)
  ensures r == 3 * x
{
  r := x * 3;
}
