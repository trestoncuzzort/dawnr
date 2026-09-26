t 1
task count_pos(s: seq) returns (r: int)
  ensures 0 <= r and r <= len(s)
method step(k: int, x: int) returns (n: int)
  requires k >= 0
  ensures n == k or n == k + 1
{
  if x > 0 {
    n := k + 1;
  } else {
    n := k;
  }
}
{
  var i: int := 0;
  r := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant 0 <= r and r <= i
    decreases len(s) - i
  {
    r := step(r, s[i]);
    i := i + 1;
  }
}
