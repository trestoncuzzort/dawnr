t 1
gate recursion
task factorial(n: int) returns (r: int)
  requires n >= 0
  ensures r == fact(n)
  decreases n
spec fun fact(n: int): int
  decreases n
= if n <= 0 then 1 else n * fact(n - 1)
{
  if n == 0 {
    r := 1;
  } else {
    r := n * factorial(n - 1);
  }
}
