t 1
task mode_transition(mode: int, cmd: int) returns (next: int)
  requires 0 <= mode and mode <= 3
  ensures 0 <= next and next <= 3
  ensures cmd == 3 ==> next == 3
  ensures cmd != 3 and mode == 3 ==> next == 3
  ensures cmd == mode + 1 and mode < 3 ==> next == cmd
  ensures cmd != 3 and cmd != mode + 1 ==> next == mode
{
  if cmd == 3 {
    next := 3;
  } else {
    if mode < 3 and cmd == mode + 1 {
      next := cmd;
    } else {
      next := mode;
    }
  }
}
