t 1
task px4_hysteresis_set(state: bool, requested: bool, last: int, time_from_true: int, time_from_false: int, new_state: bool, now: int) returns (r: bool)
  requires last >= 0 and now >= 0 and time_from_true >= 0 and time_from_false >= 0
  ensures new_state == state ==> r == state
  ensures new_state != state and requested == state and state and time_from_true == 0 ==> not r
  ensures new_state != state and requested == state and state and time_from_true > 0 ==> r
  ensures new_state != state and requested == state and not state and time_from_false == 0 ==> r
  ensures new_state != state and requested == state and not state and time_from_false > 0 ==> not r
  ensures new_state != state and requested != state and state and now >= last + time_from_true ==> not r
  ensures new_state != state and requested != state and state and now < last + time_from_true ==> r
  ensures new_state != state and requested != state and not state and now >= last + time_from_false ==> r
  ensures new_state != state and requested != state and not state and now < last + time_from_false ==> not r
{
  var req: bool := requested;
  var last_change: int := last;
  if new_state != state {
    if new_state != req {
      req := new_state;
      last_change := now;
    }
  } else {
    req := state;
  }
  r := state;
  if req != r {
    if r and not req {
      if now >= last_change + time_from_true {
        r := false;
      }
    } else {
      if not r and req {
        if now >= last_change + time_from_false {
          r := true;
        }
      }
    }
  }
}
