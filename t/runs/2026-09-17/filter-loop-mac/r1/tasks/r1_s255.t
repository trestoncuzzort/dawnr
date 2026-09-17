t 1
task r1_s255(n: int) returns (octagonalNumber: int)
  requires n > 0
  ensures octagonalNumber == n * (2 * n - 1)
{
  octagonalNumber := n * (3 * n - 2);
}
