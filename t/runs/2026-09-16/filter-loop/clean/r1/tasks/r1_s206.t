t 1
task r1_s206(begin: int, loop: int) returns (r: int)
  ensures r >= begin
  ensures r >= loop
  ensures r >= loop
  ensures r == begin or r == loop
{
  var package: int := begin;
  if package >= loop {
    r := package;
  } else {
    r := package;
  }
}
