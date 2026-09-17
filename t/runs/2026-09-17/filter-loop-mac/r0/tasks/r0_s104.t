t 1
gate loops
task r0_s104(i: int, k: int) returns (k_p: int)
  requires k == i * i
  ensures k_p == (i + 1) * (i + 1) / 2
{
  k_p := k + 2 * i;
}
