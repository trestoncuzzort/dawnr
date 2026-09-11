t 1
task probe_names_upper(Left: int, Right: int) returns (r: int)
  ensures r >= Left
  ensures r >= Right
  ensures r == Left or r == Right
{
  var Tmp: int := Left;
  if Tmp >= Right {
    r := Tmp;
  } else {
    r := Right;
  }
}
