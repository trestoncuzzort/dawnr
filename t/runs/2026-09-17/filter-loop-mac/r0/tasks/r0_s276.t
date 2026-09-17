t 1
task r0_s276(n: int) returns (star: int)
  requires n >= 0
  ensures star == 6 * n * n
{
  star := 6 * n * (n - 1) + 1;
}
