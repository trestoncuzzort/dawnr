datatype Option = Some(value: int) | None
t 1
gate loops
task discrete_log_naive(g: int, h: int, p: int) returns (res: Option)
  requires g >= 0 and h >= 0 and p >= 0
  requires p > 1
  ensures case res { Some(x) => is_discrete_log(g, h, p, x) and 0 <= x and x < p and (forall k in [0, x) . not is_discrete_log(g, h, p, k)), None => forall k in [0, p) . not is_discrete_log(g, h, p, k) }
spec fun spec_pow_mod(b: int, e: int, m: int): int
  decreases e
= if m <= 1 then 0 else if e <= 0 then 1 else (b * spec_pow_mod(b, e - 1, m)) % m
spec fun is_discrete_log(g: int, h: int, p: int, x: int): bool
  decreases 0
= p > 1 and spec_pow_mod(g, x, p) == h % p
{
  res := Option.None;
  var x: int := 0;
  var cur: int := 1;
  while x < p and res == Option.None
    invariant 0 <= x and x <= p
    invariant cur == spec_pow_mod(g, x, p)
    invariant case res { Some(y) => is_discrete_log(g, h, p, y) and 0 <= y and y < p and (forall k in [0, y) . not is_discrete_log(g, h, p, k)), None => forall k in [0, x) . not is_discrete_log(g, h, p, k) }
    decreases p - x
  {
    if cur == h % p {
      res := Option.Some(x);
    }
    cur := (g * cur) % p;
    x := x + 1;
  }
}
