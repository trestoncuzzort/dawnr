t 1
gate loops
task ac_automata_search(haystack: seq, patterns: seq<seq>) returns (results: seq<(int, int)>)
  requires len(patterns) > 0
  requires len(haystack) < 1000000
  requires len(patterns) < 1000000
  requires forall i in [0, len(patterns)) . len(patterns[i]) < 1000000
  ensures forall i in [0, len(results)) . results[i].0 >= 0 and results[i].1 >= 0 and 0 <= results[i].0 and results[i].0 < len(patterns) and matches_at(haystack, patterns[results[i].0], results[i].1)
  ensures forall pid in [0, len(patterns)) . forall idx in [0, len(haystack) + 1) . matches_at(haystack, patterns[pid], idx) ==> (exists k in [0, len(results)) . results[k] == (pid, idx))
spec fun matches_at(haystack: seq, needle: seq, start_index: int): bool
  decreases 0
= 0 <= start_index and start_index + len(needle) <= len(haystack) and (forall i in [0, len(needle)) . haystack[start_index + i] == needle[i])
inline fun patterns_view(patterns: seq<seq>): seq<seq> = patterns
{
  results := [];
  var p: int := 0;
  while p != len(patterns)
    invariant 0 <= p and p <= len(patterns)
    invariant forall k in [0, len(results)) . results[k].0 >= 0 and results[k].1 >= 0 and 0 <= results[k].0 and results[k].0 < len(patterns) and matches_at(haystack, patterns[results[k].0], results[k].1)
    invariant forall a in [0, p) . forall idx in [0, len(haystack) + 1) . matches_at(haystack, patterns[a], idx) ==> (exists k in [0, len(results)) . results[k] == (a, idx))
    decreases len(patterns) - p
  {
    var q: int := 0;
    while q != len(haystack) + 1
      invariant 0 <= p and p < len(patterns)
      invariant 0 <= q and q <= len(haystack) + 1
      invariant forall k in [0, len(results)) . results[k].0 >= 0 and results[k].1 >= 0 and 0 <= results[k].0 and results[k].0 < len(patterns) and matches_at(haystack, patterns[results[k].0], results[k].1)
      invariant forall a in [0, p) . forall idx in [0, len(haystack) + 1) . matches_at(haystack, patterns[a], idx) ==> (exists k in [0, len(results)) . results[k] == (a, idx))
      invariant forall idx in [0, q) . matches_at(haystack, patterns[p], idx) ==> (exists k in [0, len(results)) . results[k] == (p, idx))
      decreases len(haystack) + 1 - q
    {
      results := if matches_at(haystack, patterns[p], q) then results + [(p, q)] else results;
      q := q + 1;
    }
    p := p + 1;
  }
}
