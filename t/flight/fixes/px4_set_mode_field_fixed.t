t 1
task px4_set_mode_field_fixed(p: int) returns (r: int)
  requires -16777216 <= p and p <= 16777216
  ensures 0 <= p and p <= 255 ==> r == p
  ensures p < 0 or p > 255 ==> r == -1
{
  if p <= -1 or p >= 256 {
    r := -1;
  } else {
    r := p;
  }
}
