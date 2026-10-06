t 1
task count_evens_skip(s: seq) returns (c: int)
  ensures c == len([y for y in s if y % 2 == 0])
{
  c := 0;
  for i, x in s
    invariant c == len([y for y in s[0..i] if y % 2 == 0])
  {
    if x % 2 != 0 {
      continue;
    }
    c := c + 1;
  }
}
