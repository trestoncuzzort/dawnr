t 1
task px4_min3(a: int, b: int, c: int) returns (r: int)
  ensures r <= a and r <= b and r <= c
  ensures r == a or r == b or r == c
{
  var m: int := 0;
  if a < b {
    m := a;
  } else {
    m := b;
  }
  if m < c {
    r := m;
  } else {
    r := c;
  }
}
