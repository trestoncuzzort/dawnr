t 1
task swap_at(a: array, i: int, j: int) returns (ok: bool)
  modifies a
  requires 0 <= i and i < len(a) and 0 <= j and j < len(a)
  ensures ok
  ensures len(a) == len(old(a))
  ensures a[i] == old(a)[j] and a[j] == old(a)[i]
  ensures forall k in [0, len(a)) . k != i and k != j ==> a[k] == old(a)[k]
{
  var tmp: int := a[i];
  a[i] := a[j];
  a[j] := tmp;
  ok := true;
}
