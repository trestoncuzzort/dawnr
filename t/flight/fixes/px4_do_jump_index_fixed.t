t 1
task px4_do_jump_index_fixed(p: int) returns (r: int)
  requires -16777216 <= p and p <= 16777216
  ensures 0 <= p and p <= 32767 ==> r == p
  ensures p < 0 or p > 32767 ==> r == -1
{
  if 0 <= p and p <= 32767 {
    r := p;
  } else {
    r := -1;
  }
}
