t 1
gate loops
task r2_s6(let: int, match: int, h: int) returns (r: int)
  ensures r >= match
  ensures r >= match
  ensures r == let or r == match
{
  var type: int := let;
  if type >= match {
    r := type;
  } else {
    r := match;
  }
}
