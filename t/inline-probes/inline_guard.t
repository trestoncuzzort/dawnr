t 1 task inline_guard(s: seq) returns (r: int)
  ensures len(s) == 0 ==> r == 0
  ensures len(s) > 0 ==> r == s[0]
inline fun headOrZero(a: seq): int = if len(a) > 0 then a[0] else 0
{ r := headOrZero(s); }
