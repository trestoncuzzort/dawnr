t 1
gate loops
task r0_s32(x: int) returns (y: int)
  ensures 0 <= y
  ensures x < 0 ==> y == -x
{
  y := -x;
}
