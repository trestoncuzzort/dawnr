t 1
task px4_serial_control_any(data: array, buf: array, count: int) returns (n: int)
  modifies buf
  requires 0 <= count and count <= 255
  requires len(buf) >= count
  ensures n == count
  ensures forall j in [0, n) . j < len(data) ==> buf[j] == data[j]
{
  var i: int := 0;
  while i < count
    invariant 0 <= i and i <= count
    invariant forall j in [0, i) . j < len(data) ==> buf[j] == data[j]
    decreases count - i
  {
    buf[i] := data[i];
    i := i + 1;
  }
  n := i;
}
