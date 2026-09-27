t 1
task sq_bound(x: int, y: int) returns (r: int)
  requires x >= 0 and y >= 0
  ensures r >= x * y
lemma mul_le_sq(a: int, b: int)
  requires 0 <= a and 0 <= b
  ensures a * b <= (a + b) * (a + b)
{
}
{
  mul_le_sq(x, y);
  r := (x + y) * (x + y);
}
