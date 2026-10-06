t 1
task by_second(s: seq<(int, int)>) returns (r: seq<(int, int)>)
  ensures len(r) == len(s)
  ensures forall i in [0, len(r) - 1) . r[i].1 <= r[i + 1].1
  ensures forall i in [0, len(s)) . s[i] in r
{
  r := sort_by(s, p => p.1);
}
