t 1
gate quantifiers
task swap(s: seq, i: int, j: int) returns (r: seq)
  requires 0 <= i and i < len(s)
  requires 0 <= j and j < len(s)
  ensures len(r) == len(s)
  ensures r[i] == s[j]
  ensures r[j] == s[i]
  ensures forall k in [0, len(s)) . k != i and k != j ==> r[k] == s[k]
{
  var tmp: int := s[i];
  r := s[i := s[j]];
  r := r[j := tmp];
}
