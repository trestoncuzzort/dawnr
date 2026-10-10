t 1
task px4_fusion_source_any(p: int) returns (r: int)
  requires -16777216 <= p and p <= 16777216
  ensures 0 <= p and p <= 8 ==> r == p
  ensures p < 0 or p > 8 ==> r == -1
{
  var s: int := p % 256;
  if s <= 8 {
    r := s;
  } else {
    r := -1;
  }
}
