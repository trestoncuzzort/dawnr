t 1
gate loops
task r2_s276(let: int, match: int, height: int) returns (r: int)
  ensures r >= let
  ensures r >= match
  ensures r == match
{
  var type: int := let;
  if type >= match {
    r := type;
  } else {
    r := match;
  }
}
