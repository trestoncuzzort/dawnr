t 1
task clamp_sum(a: int, b: int, hi: int) returns (r: int)
  requires hi >= 0
  ensures 0 <= r and r <= hi
method clamp(x: int, h: int) returns (c: int)
  requires h >= 0
  ensures 0 <= c and c <= h
  ensures x < 0 ==> c == 0
  ensures x > h ==> c == h
  ensures 0 <= x and x <= h ==> c == x
{
  if x < 0 {
    c := 0;
  } else {
    if x > h {
      c := h;
    } else {
      c := x;
    }
  }
}
method add_clamped(x: int, y: int, h: int) returns (s: int)
  requires h >= 0
  ensures 0 <= s and s <= h
{
  var u: int := clamp(x, h);
  s := clamp(u + y, h);
}
{
  r := add_clamped(a, b, hi);
}
