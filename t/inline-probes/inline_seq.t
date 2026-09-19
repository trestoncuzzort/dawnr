t 1 task inline_seq(x: int) returns (r: seq)
  ensures len(r) == 2
  ensures r[0] == x
  ensures r[1] == x + 1
inline fun singleton(a: int): seq = [a]
inline fun consecutive(a: int): seq = singleton(a) + singleton(a + 1)
{ r := consecutive(x); }
