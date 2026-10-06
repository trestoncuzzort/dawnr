t 1
task doubled(s: seq) returns (r: seq)
  ensures len(r) == len(s)
  ensures forall i in [0, len(s)) . r[i] == 2 * s[i]
{
  r := [2 * x for x in s];
}
