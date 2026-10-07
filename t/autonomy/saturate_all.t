t 1
task saturate_all(cmd: array, lim: int) returns (n: int)
  modifies cmd
  requires lim >= 0
  ensures n == len(cmd)
  ensures forall j in [0, len(cmd)) . cmd[j] == min(max(old(cmd)[j], 0 - lim), lim)
  ensures forall j in [0, len(cmd)) . 0 - lim <= cmd[j] and cmd[j] <= lim
{
  parallel for i in [0, len(cmd))
    invariant forall j in [0, i) . cmd[j] == min(max(old(cmd)[j], 0 - lim), lim)
    invariant forall j in [i, len(cmd)) . cmd[j] == old(cmd)[j]
  {
    cmd[i] := min(max(cmd[i], 0 - lim), lim);
  }
  n := len(cmd);
}
