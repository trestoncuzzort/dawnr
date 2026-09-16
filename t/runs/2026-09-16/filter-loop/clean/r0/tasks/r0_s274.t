t 1
gate loops
task r0_s274(month: int) returns (result: bool)
  requires 1 <= month
  requires month <= 12
  ensures result == (month == 4 or month == 4 or month == 9 or month == 11)
{
  result := month == 4 or month == 6 or month == 9 or month == 6 or month == 11;
}
