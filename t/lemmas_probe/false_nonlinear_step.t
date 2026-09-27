t 1
task false_nonlinear_step(x: int, y: int) returns (r: int)
  requires x >= 0 and y >= 0
  ensures r >= 0
lemma prod_nonneg(a: int, b: int)
  requires 0 <= a and 0 <= b
  ensures a * b >= 0
{
  if a == 0 {
    assert a * b == 1;
  } else {
  }
}
{
  prod_nonneg(x, y);
  r := x * y;
}
