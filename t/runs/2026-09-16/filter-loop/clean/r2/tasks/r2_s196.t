t 1
gate loops
task r2_s196(x: int) returns (r: (int, int))
  ensures r.0 == 2 * x
  ensures r.1 == 4 * x
  ensures x == 4 * x
{
  var a: int := 0;
  var b: int := 0;
  a := 2 * x;
  b := 2 * a;
  r := (a, b);
}
