t 1 task inline_nested(x: int) returns (r: seq<seq>)
  ensures len(r) == 1
  ensures len(r[0]) == 1
  ensures r[0][0] == x
inline fun row(a: int): seq = [a]
inline fun matrix(a: int): seq<seq> = [row(a)]
{ r := matrix(x); }
