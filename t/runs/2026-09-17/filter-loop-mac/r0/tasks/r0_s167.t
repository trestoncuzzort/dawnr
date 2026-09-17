t 1
task r0_s167(l: int, w: int, h: int) returns (r: int)
  requires w > 0
  ensures r == 2 * (l + w) * h
{
  r := 2 * (l + w) * h;
}
