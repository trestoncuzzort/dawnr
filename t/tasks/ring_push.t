t 1
task ring_push(buf: array, head: int, x: int) returns (next: int)
  modifies buf
  requires len(buf) > 0 and 0 <= head and head < len(buf)
  ensures 0 <= next and next < len(buf)
  ensures next == (head + 1) % len(buf)
  ensures buf[head] == x
  ensures forall k in [0, len(buf)) . k != head ==> buf[k] == old(buf)[k]
  ensures len(buf) == len(old(buf))
{
  buf[head] := x;
  next := (head + 1) % len(buf);
}
