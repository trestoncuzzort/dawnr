t 1
task crosstrack_side(ax: int, ay: int, bx: int, by: int, px: int, py: int) returns (side: int)
  ensures side == 1 ==> (bx - ax) * (py - ay) - (by - ay) * (px - ax) > 0
  ensures side == -1 ==> (bx - ax) * (py - ay) - (by - ay) * (px - ax) < 0
  ensures side == 0 ==> (bx - ax) * (py - ay) - (by - ay) * (px - ax) == 0
  ensures side == 1 or side == -1 or side == 0
{
  var cross: int := (bx - ax) * (py - ay) - (by - ay) * (px - ax);
  if cross > 0 {
    side := 1;
  } else {
    if cross < 0 {
      side := -1;
    } else {
      side := 0;
    }
  }
}
