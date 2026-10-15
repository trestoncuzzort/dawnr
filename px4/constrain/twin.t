t 1
task constrain(x: int, lo: int, hi: int) returns (r: int)
  requires lo <= hi
  ensures lo <= r and r <= hi
  ensures (lo <= x and x <= hi) ==> r == x
{
  if x < lo { r := lo; } else { r := x; }
}
