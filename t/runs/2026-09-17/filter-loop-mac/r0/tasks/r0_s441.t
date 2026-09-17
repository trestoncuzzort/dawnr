t 1
gate loops
task r0_s441(n: int) returns (hexNum: int)
  requires n >= 0
  requires n >= 0
  ensures hexNum == n * (2 * n - 1) / 2
{
  hexNum := n * (2 * n - 1) * (2 - 1) + 1;
}
