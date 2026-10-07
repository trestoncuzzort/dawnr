t 1
task throttle_limit(cmd: int, prev: int, max_step: int) returns (out: int)
  requires max_step >= 0
  ensures prev - max_step <= out and out <= prev + max_step
  ensures prev - max_step <= cmd and cmd <= prev + max_step ==> out == cmd
{
  out := min(max(cmd, prev - max_step), prev + max_step);
}
