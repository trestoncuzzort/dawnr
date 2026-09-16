t 1
task r2_s216(base: int, height: int, length: int) returns (r: int)
  ensures r == base * height
{
  r := base * height;
}
