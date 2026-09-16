t 1
gate loops
task r1_s22(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := 3;
  r := y + x;
}
