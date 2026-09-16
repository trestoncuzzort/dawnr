t 1
gate recursion
task r1_s86(n: int) returns (star: int)
  requires n >= 0
  ensures star == 6 * n * (n - 1) + 1
{
  star := 6 * (n - 1) * (n - 1) * (n + 1) / 2;
}
