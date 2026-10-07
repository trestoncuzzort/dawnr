t 1
task stop_distance_ok(v: int, decel: int, dist: int) returns (ok: bool)
  requires v >= 0 and decel > 0 and dist >= 0
  ensures ok == (v * v <= 2 * decel * dist)
{
  ok := v * v <= 2 * decel * dist;
}
