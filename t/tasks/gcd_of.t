t 1
task gcd_of(a: int, b: int) returns (r: int)
  ensures r == gcd(a, b)
  ensures r >= 0
{
  r := gcd(a, b);
}
