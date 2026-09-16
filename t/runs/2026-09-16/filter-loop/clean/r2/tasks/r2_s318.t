t 1
gate loops
task r2_s318(x: int, y: int) returns (z: int)
  requires true
  ensures z >= x
  ensures z >= y
  ensures z >= y
{
  z := x + 1;
}
