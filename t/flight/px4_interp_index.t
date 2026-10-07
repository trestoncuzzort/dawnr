t 1
task px4_interp_index(value: int, x: seq) returns (r: int)
  requires len(x) >= 2
  ensures 0 <= r and r <= len(x) - 2
  ensures forall k in [1, r + 1) . value > x[k]
  ensures r < len(x) - 2 ==> value <= x[r + 1]
{
  var index: int := 0;
  while value > x[index + 1] and index < len(x) - 2
    invariant 0 <= index and index <= len(x) - 2
    invariant forall k in [1, index + 1) . value > x[k]
    decreases len(x) - 2 - index
  {
    index := index + 1;
  }
  r := index;
}
