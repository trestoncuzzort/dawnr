t 1
task probe_names_lean(theorem: int, have: int) returns (r: int)
  ensures r >= theorem
  ensures r >= have
  ensures r == theorem or r == have
{
  var match: int := theorem;
  if match >= have {
    r := match;
  } else {
    r := have;
  }
}
