t 1
task r1_s454(n: int) returns (octagonalNumber: int)
  requires n >= 0
  ensures octagonalNumber == n * (3 * n - 3)
{
  octagonalNumber := n * (3 * n - 2);
}
