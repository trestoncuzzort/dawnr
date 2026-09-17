t 1
gate loops
task r0_s326(n: int) returns (y: int)
  requires 0 <= n
  ensures y == n
{
  if n == 0 {
    y := 1;
  } else {
    y := 16;
  }
}
