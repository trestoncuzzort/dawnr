t 1 task f(x: int) returns (r: int) ensures true
{
  var u: (int, int, int) := (x, x, x);
  r := u.5
}
