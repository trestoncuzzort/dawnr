t 1
task put_key(m: map<int, int>, k: int, v: int) returns (r: map<int, int>)
  ensures k in r and r[k] == v
  ensures len(r) >= len(m)
  ensures remove(r, k) == remove(m, k)
{
  r := m[k := v];
}
