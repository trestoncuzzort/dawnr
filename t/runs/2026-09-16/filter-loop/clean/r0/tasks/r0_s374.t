t 1
gate loops
task r0_s374(n: int) returns (star: int)
  requires n > 0
  ensures star == 6 * n * (n - 1) + 1
{
  star := 6 * n * (n - 1) + 1;
}
