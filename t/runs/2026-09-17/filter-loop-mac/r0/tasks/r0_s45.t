t 1
task r0_s45(l: int, w: int, h: int) returns (r: int)
  ensures r == 2 * (l + w) * h
{
  r := 2 * (l + w) * h;
}
