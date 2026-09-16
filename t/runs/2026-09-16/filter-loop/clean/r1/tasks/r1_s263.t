t 1
gate loops
task r1_s263(let: int, match: int) returns (r: int)
  ensures r >= let
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
