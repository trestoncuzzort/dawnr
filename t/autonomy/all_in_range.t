t 1
task all_in_range(s: seq, lo: int, hi: int) returns (ok: bool)
  ensures ok == (forall k in [0, len(s)) . lo <= s[k] and s[k] <= hi)
{
  ok := true;
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant ok == (forall k in [0, i) . lo <= s[k] and s[k] <= hi)
    decreases len(s) - i
  {
    if s[i] < lo or s[i] > hi {
      ok := false;
    }
    i := i + 1;
  }
}
