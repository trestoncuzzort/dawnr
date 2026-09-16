t 1
gate loops
task r1_s153(n: int) returns (octagonalNumber: int)
  requires n >= 0
  ensures octagonalNumber == n * (3 * n - 3)
{
  octagonalNumber := n * (3 * n - 2);
}
