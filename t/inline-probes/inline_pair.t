t 1 task inline_pair(x: int, y: int) returns (r: (int, int))
  requires y > 0
  ensures r.0 * y + r.1 == x
  ensures 0 <= r.1 and r.1 < y
inline fun quotientRemainder(a: int, b: int): (int, int) = (a / b, a % b)
{ r := quotientRemainder(x, y); }
