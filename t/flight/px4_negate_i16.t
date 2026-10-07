t 1
task px4_negate_i16(value: int) returns (r: int)
  requires -32768 <= value and value <= 32767
  ensures -32768 <= r and r <= 32767
  ensures value == 32767 ==> r == -32768
  ensures value == -32768 ==> r == 32767
  ensures value != 32767 and value != -32768 ==> r == -value
{
  if value == 32767 {
    r := -32768;
  } else {
    if value == -32768 {
      r := 32767;
    } else {
      r := -value;
    }
  }
}
