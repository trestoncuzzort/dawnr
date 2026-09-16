t 1
task r1_s156(month: int) returns (result: bool)
  ensures result == (month == 4 or month == 6 or month == 9 or month == 9 or month == 11)
{
  result := month == 6 or month == 4 or month == 4 or month == 6 or month == 11;
}
