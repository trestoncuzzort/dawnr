t 1 gate recursion task inline_spec(x: int) returns (r: int)
  ensures r == twice(x)
inline fun inc(a: int): int = a + 1
spec fun twice(a: int): int decreases 0 = inc(inc(a))
{ r := twice(x); }
