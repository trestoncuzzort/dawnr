t 1
gate loops
task r2_s441(a: int) returns (c: int)
  requires a >= 0
  ensures c >= 0
  ensures c == a * a
{
  var i: int := 0;
  c := 1;
  while i != a
    invariant 0 <= i and i <= c
    invariant c == i * i
    decreases a - i
  {
    i := i + 1;
    i := i + 1;
  }
}
