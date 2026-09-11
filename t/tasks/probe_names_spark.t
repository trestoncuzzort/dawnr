t 1
task probe_names_spark(begin: int, loop: int) returns (r: int)
  ensures r >= begin
  ensures r >= loop
  ensures r == begin or r == loop
{
  var package: int := begin;
  if package >= loop {
    r := package;
  } else {
    r := loop;
  }
}
