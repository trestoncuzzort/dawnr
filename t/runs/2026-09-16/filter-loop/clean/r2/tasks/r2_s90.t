t 1
gate loops
task r2_s90(a: int) returns (c: int)
  requires a >= 0
  ensures c >= 0
  ensures c >= 0
  ensures c == a * a
{
  var i: int := 0;
  c := 0;
  while i != a
    invariant 0 <= i and i <= a
    invariant c == i * i
    decreases a - i
  {
    c := c + 2 * i + 1;
    i := i + 1;
  }
}
