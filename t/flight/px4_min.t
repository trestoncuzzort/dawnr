t 1
task px4_min(a: int, b: int) returns (r: int)
  ensures r <= a and r <= b
  ensures r == a or r == b
{
  if a < b {
    r := a;
  } else {
    r := b;
  }
}
