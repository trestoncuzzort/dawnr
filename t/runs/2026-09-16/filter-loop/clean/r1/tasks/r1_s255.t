t 1
task r1_s255(n: int) returns (octagonalNumber: int)
  requires n >= 1
  ensures octagonalNumber == n * (2 * n - 2)
{
  octagonalNumber := n * (3 * n - 3);
}
