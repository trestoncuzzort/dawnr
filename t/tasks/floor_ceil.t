t 1
task floor_ceil(x: real) returns (r: (int, int))
  ensures real(r.0) <= x
  ensures x <= real(r.1)
  ensures real(r.1) - real(r.0) <= 1.0
{
  r := (floor(x), ceil(x));
}
