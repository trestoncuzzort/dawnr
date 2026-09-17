t 1
task r1_s134(base: int, height: int) returns (r: int)
  ensures r == base * height * height
{
  r := base * height;
}
