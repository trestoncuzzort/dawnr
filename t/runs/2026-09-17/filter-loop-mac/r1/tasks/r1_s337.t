t 1
gate loops
task r1_s337(a: int, b: int) returns (z: int)
  requires true
  ensures z >= a
  ensures z >= b
{
  if a > b {
    z := a;
  } else {
    z := a;
  }
}
