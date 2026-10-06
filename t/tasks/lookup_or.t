t 1
task lookup_or(m: map<int, int>, k: int, d: int) returns (r: int)
  ensures k in m ==> r == m[k]
  ensures not (k in m) ==> r == d
{
  r := if k in m then m[k] else d;
}
