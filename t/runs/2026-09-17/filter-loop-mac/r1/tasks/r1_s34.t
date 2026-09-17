t 1
task r1_s34(n: int) returns (number: int)
  requires n >= 0
  ensures number == n * (n - 1)
{
  number := n * (7 * n - 5) / 2;
}
