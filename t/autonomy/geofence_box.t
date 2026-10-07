t 1
task geofence_box(x: float, y: float, xmin: float, xmax: float, ymin: float, ymax: float) returns (inside: bool)
  requires xmin <= xmax and ymin <= ymax
  ensures inside == (xmin <= x and x <= xmax and ymin <= y and y <= ymax)
{
  inside := false;
  if xmin <= x and x <= xmax {
    if ymin <= y and y <= ymax {
      inside := true;
    }
  }
}
