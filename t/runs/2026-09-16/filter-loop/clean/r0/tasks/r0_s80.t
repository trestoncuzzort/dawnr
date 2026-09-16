t 1
task r0_s80(month: int) returns (result: bool)
  ensures result == (month == 4 or month == 4 or month == 6 or month == 5 or month == 11)
{
  result := month == 4 or month == 11;
}
