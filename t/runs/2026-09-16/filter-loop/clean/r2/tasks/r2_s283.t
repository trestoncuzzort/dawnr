t 1
gate loops
task r2_s283(n: int) returns (star: int)
  requires n >= 0
  requires n > 0
  ensures star == 6 * n * (n - 1) + 1
{
  star := 6 * n * (n - 1) + 1;
}
