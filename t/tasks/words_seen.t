t 1 gate loops
task words_seen(s: seq) returns (r: set<seq>)
  ensures card(r) <= len(s.split())
  ensures forall i in [0, len(s.split())) . s.split()[i] in r
{
  var words: seq<seq> := s.split();
  var acc: set<seq> := {};
  var i: int := 0;
  while i < len(words)
    invariant 0 <= i and i <= len(words)
    invariant card(acc) <= i
    invariant forall j in [0, i) . words[j] in acc
    decreases len(words) - i
  {
    acc := union(acc, {words[i]});
    i := i + 1;
  }
  r := acc;
}
