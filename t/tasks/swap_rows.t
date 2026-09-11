t 1
gate quantifiers
task swap_rows(m: seq<seq>, i: int, j: int) returns (r: seq<seq>)
  requires 0 <= i and i < len(m)
  requires 0 <= j and j < len(m)
  ensures len(r) == len(m)
  ensures r[i] == m[j]
  ensures r[j] == m[i]
  ensures forall k in [0, len(m)) . k != i and k != j ==> r[k] == m[k]
{
  r := m[i := m[j]][j := m[i]];
}
