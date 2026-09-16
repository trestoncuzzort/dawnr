t 1
gate recursion
task r1_s190(humanYears: int) returns (dogYears_v: int)
  requires humanYears >= 0
  ensures dogYears_v == 7 * humanYears
{
  dogYears_v := 7 * humanYears;
}
