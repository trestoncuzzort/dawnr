t 1
task px4_geofence_wrap_4(i: int) returns (r: (int, int))
  requires 0 <= i and i < 4
  ensures 0 <= r.0 and r.0 < 4
  ensures 0 <= r.1 and r.1 < 4
  ensures r.0 == (if i == 0 then 3 else i - 1)
  ensures r.1 == (if i == 3 then 0 else i + 1)
{
  var prev: int := (i + 4 - 1) % 4;
  var next: int := (i + 1) % 4;
  r := (prev, next);
}
