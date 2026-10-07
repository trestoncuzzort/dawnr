t 1
task px4_wrap_bin(bin: int, bin_count: int) returns (r: int)
  requires bin_count > 0
  requires -2147483648 <= bin and bin <= 2147483647 and bin_count <= 2147483647
  requires bin + bin_count <= 2147483647
  requires bin >= -bin_count
  ensures 0 <= r and r < bin_count
  ensures r == bin % bin_count
{
  r := (bin + bin_count) % bin_count;
}
