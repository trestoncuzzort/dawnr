t 1
task px4_wrap_bin_72(bin: int) returns (r: int)
  requires -72 <= bin and bin <= 2147483647 - 72
  ensures 0 <= r and r < 72
  ensures r == bin % 72
{
  var bin_count: int := 72;
  r := (bin + bin_count) % bin_count;
}
