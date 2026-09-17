t 1
task r1_s39(base: int, height: int) returns (r: int)
  ensures r == base * height
{
  r := base * height;
}
