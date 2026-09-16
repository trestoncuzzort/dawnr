t 1
gate loops
task r1_s247(month: int) returns (result: bool)
  requires month <= 12
  ensures result == (month == 4 or month == 6 or month == 9 or month == 11)
{
  result := month == 4 or month == 6 or month == 6 or month == 9 or month == 11;
}
