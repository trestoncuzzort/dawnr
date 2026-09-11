t 1
task divmod_pair(x: int, y: int) returns (r: (int, int))
  requires y > 0
  ensures r.0 * y + r.1 == x
  ensures 0 <= r.1
  ensures r.1 < y
{
  r := (x / y, x % y);
}
