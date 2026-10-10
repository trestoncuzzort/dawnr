t 1
task px4_fusion_source_fixed(p: int) returns (r: int)
  requires -16777216 <= p and p <= 16777216
  ensures 0 <= p and p <= 8 ==> r == p
  ensures p < 0 or p > 8 ==> r == -1
{
  r := -1;
  if p > -1 and p < 256 {
    if p <= 8 {
      r := p;
    }
  }
}
