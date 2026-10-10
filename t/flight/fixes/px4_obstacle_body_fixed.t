t 1
task px4_obstacle_body_fixed(distances: array, seen: array, inc: int) returns (k: int)
  modifies seen
  requires 1 <= inc and inc <= 360
  requires len(seen) >= len(distances)
  ensures k == min(360 / inc, len(distances))
  ensures k <= len(distances) and k <= len(seen)
  ensures forall j in [0, k) . seen[j] == distances[j]
{
  var bound: int := 360 / inc;
  if len(distances) < bound {
    bound := len(distances);
  }
  var j: int := 0;
  while j < bound
    invariant 0 <= j and j <= bound
    invariant bound <= len(distances) and bound <= len(seen)
    invariant forall q in [0, j) . seen[q] == distances[q]
    decreases bound - j
  {
    seen[j] := distances[j];
    j := j + 1;
  }
  k := j;
}
