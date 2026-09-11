t 1
gate loops
task row_max_len(m: seq<seq>) returns (r: int)
  requires len(m) > 0
  ensures forall k in [0, len(m)) . len(m[k]) <= r
  ensures exists k in [0, len(m)) . len(m[k]) == r
{
  r := len(m[0]);
  var i: int := 1;
  while i < len(m)
    invariant forall j in [0, i) . j < len(m) ==> len(m[j]) <= r
    invariant exists j in [0, i) . j < len(m) and len(m[j]) == r
    invariant i >= 1
    decreases len(m) - i
  {
    if len(m[i]) > r {
      r := len(m[i]);
    } else {
    }
    i := i + 1;
  }
}
