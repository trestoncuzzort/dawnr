t 1
task px4_is_in_range(val: int, min_val: int, max_val: int) returns (r: bool)
  ensures r == (min_val <= val and val <= max_val)
{
  r := min_val <= val and val <= max_val;
}
