t 1
task rev_twice(s: seq) returns (r: seq)
  ensures len(r) == len(s)
  ensures forall k in [0, len(s)) . r[k] == s[k]
method rev(u: seq) returns (v: seq)
  ensures len(v) == len(u)
  ensures forall k in [0, len(u)) . v[k] == u[len(u) - 1 - k]
{
  v := seq(len(u), 0);
  var i: int := 0;
  while i < len(u)
    invariant len(v) == len(u)
    invariant 0 <= i and i <= len(u)
    invariant forall k in [0, i) . v[k] == u[len(u) - 1 - k]
    decreases len(u) - i
  {
    v := v[i := u[len(u) - 1 - i]];
    i := i + 1;
  }
}
{
  var w: seq := rev(s);
  r := rev(w);
}
