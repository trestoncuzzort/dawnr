t 1
task px4_wrap_bin_fixed_72(bin: int) returns (r: int)
  requires -2147483648 <= bin and bin <= 2147483647
  ensures 0 <= r and r < 72
  ensures r == bin % 72
{
  var bin_count: int := 72;
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
