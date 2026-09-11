t 1
gate recursion
task fib(n: int) returns (r: int)
  requires n >= 0
  ensures r == fibs(n)
  decreases n
spec fun fibs(n: int): int
  decreases n
= if n <= 0 then 0 else if n == 1 then 1 else fibs(n - 1) + fibs(n - 2)
{
  if n == 0 {
    r := 0;
  } else {
    if n == 1 {
      r := 1;
    } else {
      r := fib(n - 1) + fib(n - 2);
    }
  }
}
