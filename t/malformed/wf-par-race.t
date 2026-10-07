t 1
task f(a: array) returns (r: int)
  modifies a
  ensures true
{
  parallel for i in [0, len(a) - 1) {
    a[i + 1] := 0;
  }
  r := 0;
}
