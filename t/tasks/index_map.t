t 1
task index_map(s: seq) returns (m: map<int, int>)
  ensures forall i in [0, len(s)) . s[i] in m
  ensures len(m) <= len(s)
{
  m := map[];
  for i, x in s
    invariant forall j in [0, i) . s[j] in m
    invariant len(m) <= i
  {
    m := m[x := i];
  }
}
