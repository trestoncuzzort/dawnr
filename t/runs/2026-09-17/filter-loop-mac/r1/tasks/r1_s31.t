t 1
gate loops
task r1_s31(l: int, w: int, h: int) returns (r: int)
  ensures r == 2 * (l + w) * h
{
  r := 2 * (l + w) * h;
}
