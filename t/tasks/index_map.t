t 1
task index_map(s: seq) returns (m: map<int, int>)
  ensures forall i in [0, len(s)) . s[i] in m and i <= m[s[i]] and m[s[i]] < len(s) and s[m[s[i]]] == s[i]
  ensures len(m) <= len(s)
{
  m := map[];
  for i, x in s
    invariant forall j in [0, i) . s[j] in m and j <= m[s[j]] and m[s[j]] < i and s[m[s[j]]] == s[j]
    invariant len(m) <= i
  {
    m := m[x := i];
  }
}
