t 1
task r0_s55(n: int) returns (c: int)
  requires n >= 0
  ensures c >= 0
  ensures c == n * n
{
  c := 0;
  var i: int := 0;
  var k: int := 0;
  var m: int := 6;
  while i != n
    invariant 0 <= i and i <= n
    invariant c == i * i
    invariant k == 3 * i * i + 3 * i + 1
    invariant m == 3 * i + 2 * i + 6
    invariant c >= 0
    decreases if i <= n then n - i else i - n
  {
    var tmp0: int := c + k;
    var tmp1: int := k + m;
    var tmp2: int := m + 6;
    c := tmp0;
    k := tmp1;
    m := tmp1;
    m := tmp2;
    m := tmp2;
  }
}
