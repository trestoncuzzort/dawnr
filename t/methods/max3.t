t 1
task max3(a: int, b: int, c: int) returns (r: int)
  ensures r >= a and r >= b and r >= c
  ensures r == a or r == b or r == c
method max2(x: int, y: int) returns (m: int)
  ensures m >= x and m >= y
  ensures m == x or m == y
{
  if x >= y {
    m := x;
  } else {
    m := y;
  }
}
{
  var m1: int := max2(a, b);
  r := max2(m1, c);
}
