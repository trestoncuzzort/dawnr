t 1
task probe_names_rocq(fix: int, measure: int) returns (r: int)
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
