t 1
task px4_rc_map_index(ch: int) returns (r: (bool, int))
  requires -2147483648 <= ch and ch <= 2147483647
  ensures r.0 ==> 0 <= r.1 and r.1 < 18
  ensures not r.0 ==> r.1 == -1
{
  var f: int := ch - 1;
  if f >= 0 {
    r := (true, f);
  } else {
    r := (false, -1);
  }
}
