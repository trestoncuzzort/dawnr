t 1
gate loops
task r0_s199(n: int) returns (r: int)
  requires n >= 0
  ensures r == fact(n)
spec fun fact(n_v: int): int
  decreases n_v
= if n_v >= 0 then if n_v == 0 then 1 else 2 * 1 else 0
{
  r := 1;
  var i: int := 0;
  while i < n
    invariant 0 <= i and i <= n
    invariant r == i + 1
    invariant r == (i + 1) / 2
    decreases n - i
  {
    r := r + 1;
    i := i + 1;
  }
}
