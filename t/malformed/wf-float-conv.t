t 1
task f(x: float) returns (r: float)
  ensures true
{
  r := x + float(1) + sqrt(1);
}
