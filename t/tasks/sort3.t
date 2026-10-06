t 1
task sort3(a: int, b: int, c: int) returns (r: (int, int, int))
  ensures r.0 <= r.1
  ensures r.1 <= r.2
  ensures r.0 + r.1 + r.2 == a + b + c
  ensures r.0 == a or r.0 == b or r.0 == c
  ensures r.2 == a or r.2 == b or r.2 == c
{
  var lo: int := a;
  var mid: int := b;
  var hi: int := c;
  if lo > mid { lo := b; mid := a; } else { lo := a; mid := b; }
  if mid > hi { hi := mid; mid := c; } else { hi := c; }
  if lo > mid { var t2: int := lo; lo := mid; mid := t2; } else { lo := lo; }
  r := (lo, mid, hi);
}
