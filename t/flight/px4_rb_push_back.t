t 1
task px4_rb_push_back(start: int, end: int, size: int, buf_len: int) returns (r: (bool, int))
  requires size >= 1 and 0 <= start and start <= size and 0 <= end and end <= size
  requires (if start <= end then end - start else end - start + size) <= size - 1
  requires buf_len >= 0
  ensures r.0 == (buf_len >= 1 and buf_len <= size - 1 - (if start <= end then end - start else end - start + size))
  ensures r.0 ==> 0 <= r.1 and r.1 <= size
  ensures r.0 ==> (if start <= r.1 then r.1 - start else r.1 - start + size) == (if start <= end then end - start else end - start + size) + buf_len
  ensures r.0 ==> r.1 == (if end + buf_len > size then end + buf_len - size else end + buf_len)
  ensures not r.0 ==> r.1 == end
{
  if buf_len == 0 {
    return (false, end);
  }
  var e: int := end;
  if start > e {
    var available: int := start - e - 1;
    if available < buf_len {
      return (false, e);
    }
    e := e + buf_len;
  } else {
    var available: int := start - e - 1 + size;
    if available < buf_len {
      return (false, e);
    }
    var remaining_packet_len: int := size - e;
    if buf_len > remaining_packet_len {
      e := 0;
      e := e + (buf_len - remaining_packet_len);
    } else {
      e := e + buf_len;
    }
  }
  r := (true, e);
}
