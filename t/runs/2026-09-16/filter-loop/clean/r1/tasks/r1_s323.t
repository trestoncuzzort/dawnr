t 1
gate loops
task r1_s323(x: int) returns (r: int)
  ensures r == 3 * x
{
  var y: int := 2 * x;
  r := y + x;
}
