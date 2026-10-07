t 1
task px4_rb_pop_front(start: int, end: int, size: int, buf_max_len: int) returns (r: (int, int))
  requires size >= 1 and 0 <= start and start <= size and 0 <= end and end <= size
  requires (if start <= end then end - start else end - start + size) <= size - 1
  requires buf_max_len >= 0
  ensures r.0 == min((if start <= end then end - start else end - start + size), buf_max_len)
  ensures 0 <= r.1 and r.1 <= size
  ensures r.1 == (if start + r.0 > size then start + r.0 - size else start + r.0)
  ensures (if r.1 <= end then end - r.1 else end - r.1 + size) == (if start <= end then end - start else end - start + size) - r.0
{
  if start == end {
    return (0, start);
  }
  var s: int := start;
  if s < end {
    var to_copy_len: int := min(end - s, buf_max_len);
    s := s + to_copy_len;
    return (to_copy_len, s);
  } else {
    var to_copy_len: int := end - s + size;
    if to_copy_len > buf_max_len {
      to_copy_len := buf_max_len;
    }
    var remaining_buf_len: int := size - s;
    if to_copy_len > remaining_buf_len {
      s := 0;
      s := s + (to_copy_len - remaining_buf_len);
    } else {
      s := s + to_copy_len;
    }
    return (to_copy_len, s);
  }
}
