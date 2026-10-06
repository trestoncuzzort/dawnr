t 1
task weighted_sum(s: seq, w: int) returns (r: int)
  ensures r == fold((a, x) => a + w * x, 0, s)
{
  r := 0;
  for i, x in s
    invariant r == fold((a, y) => a + w * y, 0, s[0..i])
  {
    r := r + w * x;
  }
}
