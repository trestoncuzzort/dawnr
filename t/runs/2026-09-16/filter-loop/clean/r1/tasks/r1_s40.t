t 1
gate recursion
task r1_s40(fix: int, measure: int) returns (r: int)
  ensures r >= fix
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
