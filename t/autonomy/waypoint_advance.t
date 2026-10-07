t 1
task waypoint_advance(idx: int, n: int, dist2: int, accept2: int) returns (next: int)
  requires 0 <= idx and idx < n and accept2 >= 0 and dist2 >= 0
  ensures 0 <= next and next < n
  ensures dist2 <= accept2 and idx + 1 < n ==> next == idx + 1
  ensures dist2 > accept2 ==> next == idx
  ensures idx + 1 == n ==> next == idx
{
  next := idx;
  if dist2 <= accept2 {
    if idx + 1 < n {
      next := idx + 1;
    }
  }
}
