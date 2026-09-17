t 1
task r1_s496(base: int, height: int, length: int) returns (r: int)
  ensures r == base * height
{
  r := base * height * height;
}
