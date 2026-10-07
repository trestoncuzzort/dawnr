t 1
task vote3(a: float, b: float, c: float) returns (m: float)
  ensures m == a or m == b or m == c
  ensures (a <= m or b <= m) and (a <= m or c <= m) and (b <= m or c <= m)
  ensures (m <= a or m <= b) and (m <= a or m <= c) and (m <= b or m <= c)
{
  if a <= b {
    if b <= c {
      m := b;
    } else {
      if a <= c {
        m := c;
      } else {
        m := a;
      }
    }
  } else {
    if a <= c {
      m := a;
    } else {
      if b <= c {
        m := c;
      } else {
        m := b;
      }
    }
  }
}
