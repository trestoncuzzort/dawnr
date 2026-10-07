t 1
task readings_in_band(s: seq, lo: int, hi: int) returns (n: int)
  requires lo <= hi
  ensures 0 <= n and n <= len(s)
  ensures n == len([x for x in s if lo <= x and x <= hi])
{
  n := 0;
  for i, x in s
    invariant 0 <= n and n <= i
    invariant n == len([y for y in s[0..i] if lo <= y and y <= hi])
  {
    if lo <= x and x <= hi {
      n := n + 1;
    }
  }
}
