t 1
task zero_fill(buf: array) returns (n: int)
  modifies buf
  ensures n == len(buf)
  ensures forall j in [0, len(buf)) . buf[j] == 0
{
  parallel for i in [0, len(buf))
    invariant forall j in [0, i) . buf[j] == 0
  {
    buf[i] := 0;
  }
  n := len(buf);
}
