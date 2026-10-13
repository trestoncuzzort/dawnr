t 1
task px4_geofence_wrap(i: int, n: int) returns (r: (int, int))
  requires 3 <= n and n <= 2147483647
  requires 0 <= i and i < n
  requires i + n <= 2147483647
  ensures 0 <= r.0 and r.0 < n
  ensures 0 <= r.1 and r.1 < n
  ensures r.0 == (if i == 0 then n - 1 else i - 1)
  ensures r.1 == (if i == n - 1 then 0 else i + 1)
{
  var prev: int := (i + n - 1) % n;
  var next: int := (i + 1) % n;
  r := (prev, next);
}
