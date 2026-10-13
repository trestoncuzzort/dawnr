t 1
task px4_dm_offset(key_offset: int, index: int, max_index: int, item_size: int) returns (r: (bool, int))
  requires 0 <= key_offset and key_offset <= 1000000000
  requires 0 <= index and index <= 2147483647
  requires 1 <= max_index and max_index <= 100000
  requires 1 <= item_size and item_size <= 10000
  ensures r.0 == (index < max_index)
  ensures r.0 ==> r.1 == key_offset + index * item_size
  ensures r.0 ==> key_offset <= r.1 and r.1 + item_size <= key_offset + max_index * item_size
  ensures not r.0 ==> r.1 == -1
{
  if index >= max_index {
    r := (false, -1);
  } else {
    r := (true, key_offset + index * item_size);
  }
}
