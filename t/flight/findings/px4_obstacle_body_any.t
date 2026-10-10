t 1
task px4_obstacle_body_any(distances: array, seen: array, inc: int) returns (k: int)
  modifies seen
  requires 1 <= inc and inc <= 360
  requires len(seen) >= 360 / inc
  ensures k == 360 / inc
  ensures forall j in [0, k) . j < len(distances) ==> seen[j] == distances[j]
{
  var j: int := 0;
  while j < 360 / inc
    invariant 0 <= j and j <= 360 / inc
    invariant forall q in [0, j) . q < len(distances) ==> seen[q] == distances[q]
    decreases 360 / inc - j
  {
    seen[j] := distances[j];
    j := j + 1;
  }
  k := j;
}
