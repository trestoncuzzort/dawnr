t 1
task diffs(s: seq) returns (r: seq)
  requires len(s) >= 1
  ensures len(r) == len(s) - 1
  ensures forall k in [0, len(s) - 1) . r[k] == s[k + 1] - s[k]
{
  r := [s[i + 1] - s[i] for i in [0, len(s) - 1)];
}
