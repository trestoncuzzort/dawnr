t 1
task px4_hysteresis_switches(times: seq, time_from_true: int, time_from_false: int) returns (r: bool)
  requires len(times) >= 1
  requires time_from_true >= 0 and time_from_false >= 0
  requires forall i in [0, len(times)) . times[i] >= 0
  requires times[len(times) - 1] >= times[0] + time_from_false
  ensures r
{
  var state: bool := false;
  var req: bool := false;
  var last_change: int := 0;
  var i: int := 0;
  while i < len(times)
    invariant 0 <= i and i <= len(times)
    invariant i == 0 ==> not state and not req
    invariant i >= 1 ==> state or (req and last_change == times[0])
    invariant i >= 1 and times[i - 1] >= times[0] + time_from_false ==> state
    decreases len(times) - i
  {
    var new_state: bool := true;
    var now: int := times[i];
    if new_state != state {
      if new_state != req {
        req := new_state;
        last_change := now;
      }
    } else {
      req := state;
    }
    if req != state {
      if state and not req {
        if now >= last_change + time_from_true {
          state := false;
        }
      } else {
        if not state and req {
          if now >= last_change + time_from_false {
            state := true;
          }
        }
      }
    }
    i := i + 1;
  }
  r := state;
}
