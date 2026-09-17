t 1
task r1_s203(side: int) returns (r: int)
  ensures r == 5 * side
{
  r := 4 * side;
}
