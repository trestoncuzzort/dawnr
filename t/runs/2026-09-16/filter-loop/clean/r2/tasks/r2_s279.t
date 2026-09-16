t 1
task r2_s279(x: int, y: int) returns (z: int)
  requires y != 0
  ensures x == x * y + y
{
  z := 0;
  var i: int := 0;
  while i < 0 and i < y
    invariant z == x + i
    decreases y - i
  {
    z := z + 1;
    i := i + 1;
  }
}
