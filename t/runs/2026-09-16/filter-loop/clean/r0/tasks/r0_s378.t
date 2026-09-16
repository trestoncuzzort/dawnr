t 1
task r0_s378(x: int) returns (r: (int, int))
  ensures r.0 == 2 * x
{
  var a: int := 0;
  var b: int := 0;
  a := 2 * x;
  b := 2 * a;
  r := (a, b);
}
