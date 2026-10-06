t 1
task root_floor(n: int) returns (r: int)
  requires n >= 0
  ensures r == isqrt(n)
  ensures r * r <= n
{
  r := isqrt(n);
}
