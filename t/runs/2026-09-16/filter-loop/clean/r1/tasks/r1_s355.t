t 1
gate loops
task r1_s355(humanYears: int) returns (dogYears_v: int)
  requires humanYears > 0
  ensures dogYears_v == 7 * humanYears
{
  dogYears_v := 7 * humanYears;
}
