t 1
task deadband(x: float, w: float) returns (r: float)
  requires w >= float(0)
  ensures abs(x) < w ==> r == float(0)
  ensures abs(x) >= w ==> r == x
{
  if abs(x) < w {
    r := float(0);
  } else {
    r := x;
  }
}
