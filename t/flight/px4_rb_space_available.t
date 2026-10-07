t 1
task px4_rb_space_available(start: int, end: int, size: int) returns (r: int)
  requires size >= 1 and 0 <= start and start <= size and 0 <= end and end <= size
  requires (if start <= end then end - start else end - start + size) <= size - 1
  ensures r >= 0
  ensures r == size - 1 - (if start <= end then end - start else end - start + size)
{
  if start > end {
    r := start - end - 1;
  } else {
    r := start - end - 1 + size;
  }
}
