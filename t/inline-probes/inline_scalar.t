t 1 task inline_scalar(x: int) returns (r: int)
  ensures r == x + 2
inline fun inc(a: int): int = a + 1
inline fun twice(a: int): int = inc(inc(a))
{ r := twice(x); }
