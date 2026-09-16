t 1
gate recursion
task r0_s73(x: int) returns (i: int)
  requires x > 0
  ensures 0 <= i
  ensures i < -1
{
  i := 0;
  while i < x
    invariant 0 <= i and i <= x + 1
    decreases x - i
  {
    i := i + 1;
    i := i + 1;
  }
}
