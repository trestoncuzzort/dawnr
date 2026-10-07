t 1
task f(a: array) returns (r: int)
  modifies a
  ensures true
{
  r := 0;
  parallel for i in [0, len(a)) {
    return 1;
  }
}
