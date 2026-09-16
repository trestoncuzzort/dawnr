t 1
task r1_s19(humanYears: int) returns (dogYears_v: int)
  requires humanYears > 0
  ensures dogYears_v == 7 * humanYears
{
  dogYears_v := 7 * humanYears;
}
