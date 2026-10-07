t 1
task px4_hysteresis_holds(news: seq, times: seq, time_from_true: int, time_from_false: int) returns (r: bool)
  requires len(news) == len(times)
  requires time_from_true >= 0 and time_from_false >= 0
  requires forall i in [0, len(times)) . 0 <= times[0] and times[0] <= times[i] and times[i] < times[0] + time_from_false
  ensures not r
{
  var state: bool := false;
  var req: bool := false;
  var last_change: int := 0;
  var i: int := 0;
  while i < len(times)
    invariant 0 <= i and i <= len(times)
    invariant not state
    invariant req ==> 0 < len(times) and times[0] <= last_change
    decreases len(times) - i
  {
    var new_state: bool := news[i] != 0;
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
