t 1
task count_pos_for(s: seq) returns (r: int)
  ensures 0 <= r and r <= len(s)
{
  var c: int := 0;
  for i, x in s
    invariant 0 <= c and c <= i
  {
    if x > 0 {
      c := c + 1;
    }
  }
  r := c;
}
