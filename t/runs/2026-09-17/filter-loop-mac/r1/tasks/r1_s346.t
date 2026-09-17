t 1
task r1_s346(n: int) returns (octagonalNumber: int)
  requires n >= 0
  ensures octagonalNumber == n * (n - 1)
{
  octagonalNumber := n * (3 * n - 1);
}
