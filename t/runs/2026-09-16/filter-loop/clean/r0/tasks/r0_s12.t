t 1
task r0_s12(x: int) returns (r: (int, int))
  ensures r.0 == 2 * x
{
  var j: int := 0;
  var i: int := 0;
  i := 0;
  j := 0;
  while i < x
    invariant 0 <= i and i <= x
    invariant j == 2 * i
    decreases x - i
  {
    j := j + 2;
    i := i + 1;
  }
  r := (j, i);
}
