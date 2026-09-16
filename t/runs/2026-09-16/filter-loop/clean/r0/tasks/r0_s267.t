t 1
gate loops
task r0_s267(x: int, y: int) returns (r: (int, int))
  ensures r.0 == 2 * x
  ensures r.1 == 4 * x
{
  var j: int := 0;
  var i: int := 0;
  i := 0;
  j := 0;
  while i < y
    invariant 0 <= i and i <= x
    invariant j == 2 * i
    decreases x - i
  {
    j := j + 2;
    i := i + 1;
  }
}
