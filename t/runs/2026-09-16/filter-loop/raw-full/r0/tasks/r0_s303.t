t 1
gate loops
task r0_s303(n: int) returns (r: int)
  requires n >= 0
  requires n <= n
  ensures n > 0
  ensures r == n * n * (n + 1)
{
  if n == 0 {
    r := 0;
  } else {
    r := 0;
  }
}
