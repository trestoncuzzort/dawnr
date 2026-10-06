t 1
task sort_it(s: seq) returns (r: seq)
  ensures len(r) == len(s)
  ensures forall i in [0, len(r)) . forall j in [i, len(r)) . r[i] <= r[j]
{
  var u: seq := sort(s);
  r := u;
}
