t 1
gate recursion
task f(n: int) returns (r: int)
  requires n >= 0
  ensures r == 0
  decreases true
{
  if n == 0 {
    r := 0;
  } else {
    r := f(n - 1);
  }
}
