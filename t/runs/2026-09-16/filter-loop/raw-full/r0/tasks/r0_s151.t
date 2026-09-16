t 1
gate recursion
task r0_s151(n: int) returns (r: int)
  requires n >= 0
  ensures r == n * (n + 1) * (n + 1) * (n + 1) / 2
{
  if n == 0 {
    r := 1;
  } else {
    r := 0;
  }
}
