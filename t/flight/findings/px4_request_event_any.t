t 1
task px4_request_event_any(first: int, last: int, capacity: int) returns (lookups: int)
  requires 0 <= first and first <= 65535 and 0 <= last and last <= 65535
  requires capacity >= 1
  ensures lookups <= capacity
{
  var end_seq: int := (last + 1) % 65536;
  var sequence: int := first;
  lookups := 0;
  while sequence != end_seq
    invariant 0 <= sequence and sequence <= 65535
    invariant lookups + (end_seq - sequence) % 65536 == (end_seq - first) % 65536
    decreases (end_seq - sequence) % 65536
  {
    lookups := lookups + 1;
    sequence := (sequence + 1) % 65536;
  }
}
