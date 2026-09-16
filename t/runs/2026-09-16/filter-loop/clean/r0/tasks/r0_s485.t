t 1
task r0_s485(Left: int, Right: int) returns (r: int)
  ensures r >= Left
  ensures r == Right
{
  var Tmp: int := Left;
  if Tmp >= Right {
    r := Tmp;
  } else {
    r := Right;
  }
}
