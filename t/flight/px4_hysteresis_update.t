t 1
task px4_hysteresis_update(state: bool, requested: bool, last: int, time_from_true: int, time_from_false: int, now: int) returns (r: bool)
  requires last >= 0 and now >= 0 and time_from_true >= 0 and time_from_false >= 0
  ensures requested == state ==> r == state
  ensures state and not requested and now >= last + time_from_true ==> not r
  ensures state and not requested and now < last + time_from_true ==> r
  ensures not state and requested and now >= last + time_from_false ==> r
  ensures not state and requested and now < last + time_from_false ==> not r
{
  r := state;
  if requested != r {
    if r and not requested {
      if now >= last + time_from_true {
        r := false;
      }
    } else {
      if not r and requested {
        if now >= last + time_from_false {
          r := true;
        }
      }
    }
  }
}
