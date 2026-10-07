t 1
task px4_lerp(a: float, b: float, s: float) returns (r: float)
  requires abs(a) <= float(1000000) and abs(b) <= float(1000000) and abs(s) <= float(1000000)
  ensures s == float(0) ==> r == a
  ensures s == float(1) ==> r == b
  ensures r == (float(1) - s) * a + s * b
{
  r := (float(1) - s) * a + s * b;
}
