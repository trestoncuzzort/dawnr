t 1
task is_in_range(x: int, lo: int, hi: int) returns (r: bool)
  requires lo <= hi
  ensures r == (lo <= x and x <= hi)
{
  r := lo <= x and x <= hi;
}
