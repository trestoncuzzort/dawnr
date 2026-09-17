t 1
gate recursion
task r0_s256(x: int) returns (r: (int, int))
  ensures r.0 == 2 * x
  ensures r.1 == 3 * x
{
  var a: int := 0;
  var b: int := 0;
  a := 0;
  a := 2 * x;
  b := 2 * a;
  r := (a, b);
}
