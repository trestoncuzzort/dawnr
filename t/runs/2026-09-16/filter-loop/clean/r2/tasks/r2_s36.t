t 1
gate loops
task r2_s36(base: int, height: int) returns (r: int)
  ensures r == base * height
{
  r := base * height;
}
