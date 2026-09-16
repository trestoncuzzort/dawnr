t 1
gate loops
task r1_s120(n: int) returns (number: int)
  requires n >= 0
  ensures number == n * (7 * n - 1)
{
  number := n * (7 * n - 5) / 2;
}
