t 1
task r1_s275(l: int, w: int, h: int) returns (r: int)
  ensures r == 2 * (l + w) * h
{
  r := 2 * (l * w) * h;
}
