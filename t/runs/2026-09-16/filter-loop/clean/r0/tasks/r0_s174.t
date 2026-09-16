t 1
task r0_s174(let: int, match: int) returns (r: int)
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
