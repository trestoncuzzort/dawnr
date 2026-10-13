t 1
task px4_rc_map_index(chan: int) returns (r: (bool, int))
  requires -2147483648 <= chan and chan <= 2147483647
  ensures r.0 == (1 <= chan and chan <= 18)
  ensures r.0 ==> 0 <= r.1 and r.1 < 18
  ensures r.0 ==> r.1 == chan - 1
  ensures not r.0 ==> r.1 == -1
{
  if chan >= 1 and chan <= 18 {
    r := (true, chan - 1);
  } else {
    r := (false, -1);
  }
}
