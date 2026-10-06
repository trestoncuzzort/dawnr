t 1
gate loops
task binary_search(s: seq, target: int) returns (result: int)
  requires len(s) <= 2147483647
  requires is_sorted(s)
  ensures result >= 0
  ensures result <= len(s)
  ensures forall i in [0, result) . s[i] < target
  ensures forall i in [result, len(s)) . s[i] >= target
spec fun is_sorted(q: seq): bool
  decreases 0
= forall i in [0, len(q)) . forall j in [i, len(q)) . q[i] <= q[j]
{
  var lo: int := 0;
  var hi: int := len(s);
  while lo < hi
    invariant 0 <= lo and lo <= hi and hi <= len(s)
    invariant forall i in [0, lo) . s[i] < target
    invariant forall i in [hi, len(s)) . s[i] >= target
    decreases hi - lo
  {
    var mid: int := lo + (hi - lo) / 2;
    if s[mid] < target {
      lo := mid + 1;
    } else {
      hi := mid;
    }
  }
  result := lo;
}
