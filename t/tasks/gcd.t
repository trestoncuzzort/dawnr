t 1
gate recursion
task gcd(a: int, b: int) returns (r: int)
  requires a >= 0
  requires b >= 0
  ensures r == gcds(a, b)
  decreases a + b
spec fun gcds(a: int, b: int): int
  decreases a + b
= if a <= 0 then b else if b <= 0 then a else if a > b then gcds(a - b, b) else if b > a then gcds(a, b - a) else a
{
  if a == 0 {
    r := b;
  } else {
    if b == 0 {
      r := a;
    } else {
      if a > b {
        r := gcd(a - b, b);
      } else {
        if b > a {
          r := gcd(a, b - a);
        } else {
          r := a;
        }
      }
    }
  }
}
