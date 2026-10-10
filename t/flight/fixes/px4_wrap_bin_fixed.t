t 1
task px4_wrap_bin_fixed(bin: int, bin_count: int) returns (r: int)
  requires bin_count > 0
  requires -2147483648 <= bin and bin <= 2147483647 and bin_count <= 2147483647
  ensures 0 <= r and r < bin_count
  ensures r == bin % bin_count
{
  var wrapped: int := 0;
  if bin >= 0 {
    wrapped := bin % bin_count;
  } else {
    wrapped := -((-bin) % bin_count);
  }
  if wrapped < 0 {
    r := wrapped + bin_count;
  } else {
    r := wrapped;
  }
}
