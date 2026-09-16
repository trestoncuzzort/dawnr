t 1
gate loops
task r0_s455(month: int) returns (result: bool)
  requires 1 <= month
  ensures result == (month == 1 or month == 4 or month == 11)
{
  result := month == 4 or month == 11;
}
