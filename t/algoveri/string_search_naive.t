t 1
gate loops
task string_search_naive(haystack: seq, needle: seq) returns (indices: seq)
  requires len(haystack) < 1000000
  requires len(needle) < 1000000
  ensures forall k in [0, len(indices)) . indices[k] >= 0
  ensures forall i in [0, len(indices)) . matches_at(haystack, needle, indices[i])
  ensures forall i in [0, len(haystack) + 1) . matches_at(haystack, needle, i) ==> (exists k in [0, len(indices)) . indices[k] == i)
spec fun char_eq(hs: seq, nd: seq, start_index: int, i: int): bool
  decreases 0
= 0 <= i and i < len(nd) and 0 <= start_index + i and start_index + i < len(hs) and hs[start_index + i] == nd[i]
spec fun matches_at(hs: seq, nd: seq, start_index: int): bool
  decreases 0
= 0 <= start_index and start_index + len(nd) <= len(hs) and (forall i in [0, len(nd)) . char_eq(hs, nd, start_index, i))
{
  indices := [];
  var pos: int := 0;
  while pos + len(needle) <= len(haystack)
    invariant 0 <= pos
    invariant forall k in [0, len(indices)) . indices[k] >= 0
    invariant forall k in [0, len(indices)) . matches_at(haystack, needle, indices[k])
    invariant forall p in [0, pos) . matches_at(haystack, needle, p) ==> (exists k in [0, len(indices)) . indices[k] == p)
    decreases len(haystack) - pos
  {
    var j: int := 0;
    while j < len(needle) and char_eq(haystack, needle, pos, j)
      invariant 0 <= j and j <= len(needle)
      invariant forall k in [0, j) . char_eq(haystack, needle, pos, k)
      decreases len(needle) - j
    {
      j := j + 1;
    }
    if j == len(needle) {
      indices := indices + [pos];
    }
    pos := pos + 1;
  }
}
