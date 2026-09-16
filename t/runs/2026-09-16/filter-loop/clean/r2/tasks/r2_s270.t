t 1
gate loops
task r2_s270(fix: int, measure: int) returns (r: int)
  ensures r >= fix
  ensures r >= measure
  ensures r >= measure
  ensures r >= measure
  ensures r >= measure
  ensures r == fix or r == measure
{
  var cofix: int := fix;
  if cofix >= measure {
    r := cofix;
  } else {
    r := measure;
  }
}
