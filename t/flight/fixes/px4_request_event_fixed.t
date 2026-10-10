t 1
task px4_request_event_fixed(first: int, last: int, capacity: int) returns (lookups: int)
  requires 0 <= first and first <= 65535 and 0 <= last and last <= 65535
  requires 1 <= capacity and capacity <= 65535
  ensures lookups <= capacity
  ensures lookups == min((last + 1 - first) % 65536, capacity)
{
  var end_seq: int := (last + 1) % 65536;
  var sequence: int := first;
  var requested: int := (end_seq - sequence) % 65536;
  if requested > capacity {
    sequence := (end_seq - capacity) % 65536;
  }
  lookups := 0;
  while sequence != end_seq
    invariant 0 <= sequence and sequence <= 65535
    invariant lookups + (end_seq - sequence) % 65536 == min(requested, capacity)
    decreases (end_seq - sequence) % 65536
  {
    lookups := lookups + 1;
    sequence := (sequence + 1) % 65536;
  }
}
