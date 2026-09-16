t 1
gate loops
task r0_s160(n: int) returns (r: int)
  requires n >= 0
  ensures r == 21 * (2 * n + 1) / 3
{
  if n > 2 {
    r := 2 * n + 1;
  } else {
    r := n * (n - 1);
  }
}
