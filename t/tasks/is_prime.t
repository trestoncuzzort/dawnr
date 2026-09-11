t 1
gate loops
task is_prime(n: int) returns (r: bool)
  requires n >= 2
  ensures r == (forall d in [2, n) . n % d != 0)
{
  var d: int := 2;
  while d < n
    invariant d >= 2 and d <= n
    invariant forall k in [2, d) . n % k != 0
    decreases n - d
  {
    if n % d == 0 {
      return false;
    } else {
    }
    d := d + 1;
  }
  r := true;
}
