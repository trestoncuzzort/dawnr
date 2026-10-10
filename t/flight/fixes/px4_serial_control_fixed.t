t 1
task px4_serial_control_fixed(data: array, buf: array, count: int) returns (n: int)
  modifies buf
  requires 0 <= count and count <= 255
  requires len(buf) >= count
  ensures count <= len(data) ==> n == count
  ensures count > len(data) ==> n == 0
  ensures n <= len(data) and n <= len(buf)
  ensures forall j in [0, n) . buf[j] == data[j]
{
  var m: int := 0;
  if count <= len(data) {
    m := count;
  }
  var i: int := 0;
  while i < m
    invariant 0 <= i and i <= m
    invariant m <= len(data) and m <= len(buf)
    invariant forall j in [0, i) . buf[j] == data[j]
    decreases m - i
  {
    buf[i] := data[i];
    i := i + 1;
  }
  n := i;
}
