t 1
task r1_s268(n: int) returns (octagonalNumber: int)
  requires n >= 0
  ensures octagonalNumber == n * (3 * n - 2)
{
  octagonalNumber := n * (3 * n - 5) / 2;
}
